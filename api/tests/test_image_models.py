"""Tests for the image-model allow-list / resolution (#49)."""

import pytest

from app import image_models as im


def test_catalog_has_builtins_including_anythingxl():
    names = {m.name for m in im.catalog({})}
    assert "anything-v5.safetensors" in names
    assert "AnythingXL_v50.safetensors" in names
    anyxl = next(m for m in im.catalog({}) if m.name == "AnythingXL_v50.safetensors")
    assert anyxl.type == "sdxl"  # AnythingXL is SDXL -> needs the SDXL workflow


def test_resolve_known_and_default():
    assert im.resolve("anything-v5.safetensors", {}).name == "anything-v5.safetensors"
    # None resolves to the configured default.
    assert im.resolve(None, {}).name == im.default_name({})


def test_resolve_rejects_unknown_and_path_traversal():
    for bad in ["../../etc/passwd", "evil.safetensors", "/abs/path.ckpt"]:
        with pytest.raises(ValueError):
            im.resolve(bad, {})


def test_default_name_follows_sd_checkpoint_and_type():
    assert (
        im.default_name({"SD_CHECKPOINT": "anything-v5.safetensors"}) == "anything-v5.safetensors"
    )
    assert im.default_name({"SD_MODEL_TYPE": "sdxl"}) == "sdxl.safetensors"
    assert im.default_name({}) == "anything-v5.safetensors"


def test_sd_models_env_extends_catalog_and_is_selectable():
    env = {"SD_MODELS": "custom.safetensors:sdxl:My Custom"}
    m = im.resolve("custom.safetensors", env)
    assert m.type == "sdxl"
    assert m.label == "My Custom"
    # A configured custom default is always allowed even if not in SD_MODELS.
    env2 = {"SD_CHECKPOINT": "mine.safetensors"}
    assert im.resolve(None, env2).name == "mine.safetensors"
    assert im.resolve("mine.safetensors", env2).name == "mine.safetensors"
