"""Allowed image-generation checkpoints and their workflow type (#49).

Per-request model selection is restricted to an allow-list so a request can't
inject an arbitrary file path / unknown checkpoint into the ComfyUI workflow.
Each model declares its type (``sd15`` | ``sdxl``) which selects the workflow,
sampler and resolution downstream.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

EnvLike = Mapping[str, str] | None


@dataclass(frozen=True)
class ImageModel:
    name: str  # checkpoint filename passed to ComfyUI (CheckpointLoaderSimple)
    type: str  # "sd15" | "sdxl" -> selects workflow / sampler / resolution
    label: str  # human-readable label for the UI dropdown


# Built-in catalog. AnythingXL_v50 is an SDXL checkpoint (#49); it must render
# with the SDXL workflow (1024px / dpmpp_2m) to look right.
_BUILTIN: tuple[ImageModel, ...] = (
    ImageModel("anything-v5.safetensors", "sd15", "Anything v5 (SD 1.5)"),
    ImageModel("sdxl.safetensors", "sdxl", "SDXL base"),
    ImageModel("AnythingXL_v50.safetensors", "sdxl", "AnythingXL v5.0 (SDXL)"),
)


def _env(env: EnvLike) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _norm_type(value: str) -> str:
    return "sdxl" if (value or "").strip().lower() == "sdxl" else "sd15"


def default_type(env: EnvLike = None) -> str:
    return _norm_type(_env(env).get("SD_MODEL_TYPE", "sd15"))


def default_name(env: EnvLike = None) -> str:
    e = _env(env)
    ckpt = e.get("SD_CHECKPOINT")
    if ckpt:
        return ckpt
    return "sdxl.safetensors" if default_type(e) == "sdxl" else "anything-v5.safetensors"


def catalog(env: EnvLike = None) -> list[ImageModel]:
    """Allowed models: the built-ins plus any from the SD_MODELS env.

    SD_MODELS is a comma-separated list of ``name:type[:label]`` entries
    (type defaults to sd15, label to name). The configured default checkpoint
    is always included so it is selectable.
    """
    e = _env(env)
    by_name: dict[str, ImageModel] = {m.name: m for m in _BUILTIN}
    for entry in (p.strip() for p in e.get("SD_MODELS", "").split(",") if p.strip()):
        parts = entry.split(":")
        name = parts[0].strip()
        if not name:
            continue
        type_ = _norm_type(parts[1]) if len(parts) > 1 else "sd15"
        label = parts[2].strip() if len(parts) > 2 and parts[2].strip() else name
        by_name[name] = ImageModel(name, type_, label)
    d = default_name(e)
    by_name.setdefault(d, ImageModel(d, default_type(e), d))
    return list(by_name.values())


def resolve(name: str | None, env: EnvLike = None) -> ImageModel:
    """Return the ImageModel for ``name`` (or the default when None).

    Raises ValueError if ``name`` is not in the allow-list — this is what keeps
    a caller from pointing the worker at an arbitrary checkpoint / file path.
    """
    e = _env(env)
    target = name if name else default_name(e)
    for m in catalog(e):
        if m.name == target:
            return m
    raise ValueError(f"image model not allowed: {target!r}")
