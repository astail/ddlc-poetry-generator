"""ComfyUI HTTP client + worker processor (issue #12).

Submits the txt2img workflow (mirrors comfyui/workflows/poem_sd15.json) to a
running ComfyUI server, waits for completion, downloads the image, and saves it
under DATA_DIR/images. Used as the worker-gpu processor.
"""

from __future__ import annotations

import copy
import logging
import os
import random
import time
from pathlib import Path
from typing import Callable, Mapping, Optional

import httpx

from .image_models import ImageModel
from .image_models import default_name as default_image_model
from .image_models import default_type as image_default_type
from .image_models import resolve as resolve_image_model
from .models import Image

logger = logging.getLogger(__name__)

# Quality tags always prepended to the positive prompt so every generation gets
# a consistent quality floor regardless of what the poem step produced (#96).
QUALITY_PREFIX = (
    "{{{masterpiece}}}, {{{best quality}}}, {{ultra-detailed}}, {illustration}, "
    "{{an extremely delicate and beautiful}}, high quality, very_high_resolution, "
    "large_filesize, full color"
)

# Baseline negative prompt always applied to every image (#96). The per-poem
# negative (if any) is appended after this. Replaces the old minimal default.
BASE_NEGATIVE = (
    "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, "
    "fewer digits, cropped, worst quality, low quality, normal quality, "
    "jpeg artifacts, signature, watermark, username, blurry, artist name, "
    "multiple legs, malformation, multiple angle, longbody, pubic hair, "
    "missing arms, head_out_of_frame, 2koma, panel layout"
)


def with_quality_prefix(prompt: str) -> str:
    """Lead with the mandatory quality tags, then the per-poem prompt (#96)."""
    prompt = (prompt or "").strip().rstrip(",").strip()
    return f"{QUALITY_PREFIX}, {prompt}" if prompt else QUALITY_PREFIX


def with_base_negative(negative: str) -> str:
    """Always apply the baseline negative, then any per-poem negative (#96)."""
    negative = (negative or "").strip().rstrip(",").strip()
    return f"{BASE_NEGATIVE}, {negative}" if negative else BASE_NEGATIVE


# Mirrors comfyui/workflows/poem_sd15.json (kept in code so the worker image is
# self-contained). Fields are overwritten per-request in generate().
DEFAULT_WORKFLOW: dict = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": 25,
            "cfg": 7,
            "sampler_name": "euler_ancestral",
            "scheduler": "normal",
            "denoise": 1.0,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0],
        },
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {"ckpt_name": "anything-v5.safetensors"},
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {"width": 512, "height": 512, "batch_size": 1},
    },
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": BASE_NEGATIVE, "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {
        "class_type": "SaveImage",
        "inputs": {"filename_prefix": "ddlc_poem", "images": ["8", 0]},
    },
}

# SDXL variant (#22): same graph, 1024px, dpmpp_2m/karras. CheckpointLoaderSimple
# loads a single-file SDXL checkpoint. On a 6GB card ComfyUI must run --lowvram
# (set in comfyui/Dockerfile), which offloads weights between CPU/GPU — slower
# but it fits.
SDXL_WORKFLOW: dict = copy.deepcopy(DEFAULT_WORKFLOW)
SDXL_WORKFLOW["3"]["inputs"]["sampler_name"] = "dpmpp_2m"
SDXL_WORKFLOW["3"]["inputs"]["scheduler"] = "karras"
SDXL_WORKFLOW["3"]["inputs"]["steps"] = 30
SDXL_WORKFLOW["5"]["inputs"]["width"] = 1024
SDXL_WORKFLOW["5"]["inputs"]["height"] = 1024
SDXL_WORKFLOW["4"]["inputs"]["ckpt_name"] = "sdxl.safetensors"


def workflow_for(model_type: str) -> dict:
    return SDXL_WORKFLOW if (model_type or "").lower() == "sdxl" else DEFAULT_WORKFLOW


class ComfyUIClient:
    def __init__(
        self,
        base_url: str,
        *,
        http: Optional[httpx.Client] = None,
        data_dir: Path | str = "/data",
        workflow: Optional[dict] = None,
        poll_interval: float = 1.0,
        timeout: float = 180.0,
    ):
        self._base = base_url.rstrip("/")
        self._http = http or httpx.Client(timeout=30)
        self._data_dir = Path(data_dir)
        self._workflow = workflow or DEFAULT_WORKFLOW
        self._poll_interval = poll_interval
        self._timeout = timeout

    def generate(
        self,
        *,
        prompt: str,
        negative: str = "",
        checkpoint: str,
        seed: int = 0,
        steps: int = 25,
        cfg: float = 7,
        width: int = 512,
        height: int = 512,
        workflow: Optional[dict] = None,
    ) -> str:
        # `workflow` lets the caller pick a per-request graph (e.g. SDXL vs
        # SD1.5 for a selected model); falls back to the client's default.
        wf = copy.deepcopy(workflow if workflow is not None else self._workflow)
        wf["4"]["inputs"]["ckpt_name"] = checkpoint
        # Always inject the quality prefix + baseline negative so image
        # generation stays stable regardless of the per-poem prompts (#96).
        wf["6"]["inputs"]["text"] = with_quality_prefix(prompt)
        wf["7"]["inputs"]["text"] = with_base_negative(negative)
        wf["3"]["inputs"]["seed"] = seed
        wf["3"]["inputs"]["steps"] = steps
        wf["3"]["inputs"]["cfg"] = cfg
        wf["5"]["inputs"]["width"] = width
        wf["5"]["inputs"]["height"] = height

        resp = self._http.post(f"{self._base}/prompt", json={"prompt": wf})
        resp.raise_for_status()
        prompt_id = resp.json()["prompt_id"]

        outputs = self._await_outputs(prompt_id)
        images = self._extract_images(outputs)
        if not images:
            raise RuntimeError(
                f"ComfyUI returned no image for prompt {prompt_id} "
                "(cached run with empty outputs, or workflow has no SaveImage node)"
            )
        img = images[0]
        data = self._fetch_view(img)

        out_dir = self._data_dir / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{prompt_id}_{img['filename']}"
        out_path.write_bytes(data)
        logger.info("saved image %s (%d bytes)", out_path, len(data))
        return str(out_path)

    def _await_outputs(self, prompt_id: str) -> dict:
        deadline = time.monotonic() + self._timeout
        while time.monotonic() < deadline:
            resp = self._http.get(f"{self._base}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()
            entry = history.get(prompt_id)
            if entry is not None:
                self._raise_if_failed(prompt_id, entry.get("status"))
                return entry.get("outputs", {})
            time.sleep(self._poll_interval)
        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish in time")

    @staticmethod
    def _raise_if_failed(prompt_id: str, status: Optional[dict]) -> None:
        """Surface a ComfyUI execution error (OOM, missing checkpoint, bad node)
        with its real reason instead of letting it fall through to the generic
        "no image" below. ComfyUI records the failure in the history entry's
        ``status`` (``status_str == "error"`` plus an ``execution_error`` message).
        """
        if not isinstance(status, dict) or status.get("status_str") != "error":
            return
        detail = None
        for msg in status.get("messages") or []:
            if isinstance(msg, (list, tuple)) and len(msg) == 2 and msg[0] == "execution_error":
                data = msg[1] or {}
                node = data.get("node_type") or data.get("node_id")
                exc = data.get("exception_message") or data.get("exception_type")
                detail = ": ".join(
                    p for p in (str(node) if node else "", str(exc) if exc else "") if p
                )
                break
        raise RuntimeError(f"ComfyUI prompt {prompt_id} failed: {detail or 'execution error'}")

    @staticmethod
    def _extract_images(outputs: dict) -> list[dict]:
        for node in outputs.values():
            if isinstance(node, dict) and node.get("images"):
                return node["images"]
        return []

    def _fetch_view(self, img: dict) -> bytes:
        resp = self._http.get(
            f"{self._base}/view",
            params={
                "filename": img["filename"],
                "subfolder": img.get("subfolder", ""),
                "type": img.get("type", "output"),
            },
        )
        resp.raise_for_status()
        return resp.content


def make_comfyui_processor(
    client: ComfyUIClient,
    *,
    checkpoint: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Callable[[Image], str]:
    """Adapt a ComfyUIClient into a worker `processor` (Image -> path).

    The checkpoint comes from ``image.checkpoint`` (per-request model selection,
    #49) and falls back to ``checkpoint`` / the configured default. The model's
    type (sd15/sdxl, from the allow-list) selects the workflow + resolution so a
    selected SDXL model renders at 1024px with the SDXL sampler.
    """
    resolved_env = env if env is not None else os.environ
    fallback = checkpoint or default_image_model(resolved_env)

    def processor(image: Image) -> str:
        name = image.checkpoint or fallback
        try:
            model = resolve_image_model(name, resolved_env)
        except ValueError:
            # Shouldn't happen (the API validates against the allow-list), but
            # don't crash the worker on a stale/unknown name.
            model = ImageModel(name, image_default_type(resolved_env), name)
        wf = workflow_for(model.type)
        sdxl = model.type == "sdxl"
        # Resolution is driven by the model type (SDXL needs 1024 to look right),
        # NOT image.width — that column defaults to 512, so `image.width or ...`
        # would always win and silently render SDXL at 512.
        width = int(resolved_env.get("SD_WIDTH", "1024" if sdxl else "512"))
        height = int(resolved_env.get("SD_HEIGHT", "1024" if sdxl else "512"))
        # A fresh seed on every attempt. Re-submitting an identical workflow makes
        # ComfyUI serve a cached run whose /history outputs are empty ("Prompt
        # executed in 0.00 seconds"), which we'd misread as "ComfyUI returned no
        # image". Because a persisted seed is reused on retry, that turned any
        # transient first-attempt failure into a permanent one. The API never
        # pins a seed, so randomizing here is safe and makes a retry a real
        # re-render. The seed actually used is recorded below (#66).
        # Bounded to a signed 32-bit int: Image.seed is a Postgres INTEGER, so a
        # value above 2**31-1 raises NumericValueOutOfRange on commit (and 2**31
        # of seeds is ample to avoid cache collisions).
        image.seed = random.randint(0, 2**31 - 1)
        image.checkpoint = name  # provenance (#66)
        image.width = width  # record the size actually generated
        image.height = height
        return client.generate(
            workflow=wf,
            prompt=image.prompt,
            negative=image.negative,
            checkpoint=name,
            seed=image.seed,
            steps=int(resolved_env.get("SD_STEPS", "30" if sdxl else "25")),
            cfg=float(resolved_env.get("SD_CFG", "7")),
            width=width,
            height=height,
        )

    return processor
