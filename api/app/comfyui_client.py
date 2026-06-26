"""ComfyUI HTTP client + worker processor (issue #12).

Submits the txt2img workflow (mirrors comfyui/workflows/poem_sd15.json) to a
running ComfyUI server, waits for completion, downloads the image, and saves it
under DATA_DIR/images. Used as the worker-gpu processor.
"""

from __future__ import annotations

import copy
import logging
import random
import time
from pathlib import Path
from typing import Callable, Optional

import httpx

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
    "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "anything-v5.safetensors"}},
    "5": {"class_type": "EmptyLatentImage", "inputs": {"width": 512, "height": 512, "batch_size": 1}},
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": DEFAULT_NEGATIVE, "clip": ["4", 1]}},
    "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
    "9": {"class_type": "SaveImage", "inputs": {"filename_prefix": "ddlc_poem", "images": ["8", 0]}},
}


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
    ) -> str:
        wf = copy.deepcopy(self._workflow)
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
    checkpoint: str,
    steps: int = 25,
    cfg: float = 7,
    width: int = 512,
    height: int = 512,
) -> Callable[[Image], str]:
    """Adapt a ComfyUIClient into a worker `processor` (Image -> path)."""

    def processor(image: Image) -> str:
        if image.seed is None:
            image.seed = random.randint(0, 2**32 - 1)  # recorded on commit
        return client.generate(
            prompt=image.prompt,
            negative=image.negative,
            checkpoint=checkpoint,
            seed=image.seed,
            steps=steps,
            cfg=cfg,
            width=image.width or width,
            height=image.height or height,
        )

    return processor
