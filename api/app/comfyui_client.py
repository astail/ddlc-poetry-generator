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

DEFAULT_NEGATIVE = "lowres, bad anatomy, extra fingers, watermark, text"

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
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": DEFAULT_NEGATIVE, "clip": ["4", 1]}},
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
        wf["6"]["inputs"]["text"] = prompt
        wf["7"]["inputs"]["text"] = negative or DEFAULT_NEGATIVE
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
            raise RuntimeError("ComfyUI returned no image")
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
            if prompt_id in history:
                return history[prompt_id].get("outputs", {})
            time.sleep(self._poll_interval)
        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not finish in time")

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
        if image.seed is None:
            image.seed = random.randint(0, 2**32 - 1)  # recorded on commit
        image.checkpoint = name  # provenance (#66)
        return client.generate(
            workflow=wf,
            prompt=image.prompt,
            negative=image.negative,
            checkpoint=name,
            seed=image.seed,
            steps=int(resolved_env.get("SD_STEPS", "30" if sdxl else "25")),
            cfg=float(resolved_env.get("SD_CFG", "7")),
            width=image.width or int(resolved_env.get("SD_WIDTH", "1024" if sdxl else "512")),
            height=image.height or int(resolved_env.get("SD_HEIGHT", "1024" if sdxl else "512")),
        )

    return processor
