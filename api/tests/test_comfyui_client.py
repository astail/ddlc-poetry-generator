import json

import httpx
import pytest

from app.comfyui_client import (
    BASE_NEGATIVE,
    QUALITY_PREFIX,
    ComfyUIClient,
    make_comfyui_processor,
)
from app.models import Image


def _make_client(tmp_path, captured):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/prompt":
            captured["workflow"] = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "abc"})
        if path == "/history/abc":
            return httpx.Response(
                200,
                json={
                    "abc": {
                        "outputs": {
                            "9": {
                                "images": [{"filename": "x.png", "subfolder": "", "type": "output"}]
                            }
                        }
                    }
                },
            )
        if path == "/view":
            captured["view_params"] = dict(request.url.params)
            return httpx.Response(200, content=b"PNGDATA")
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    return ComfyUIClient("http://comfyui:8188", http=http, data_dir=tmp_path, poll_interval=0)


def test_generate_saves_image_and_substitutes_workflow(tmp_path):
    captured = {}
    client = _make_client(tmp_path, captured)
    path = client.generate(
        prompt="moonlit shore, 1girl",
        negative="blurry",
        checkpoint="my-model.safetensors",
        seed=123,
        steps=20,
        cfg=6,
        width=640,
        height=384,
    )
    # file written with the returned bytes
    assert path.endswith("abc_x.png")
    with open(path, "rb") as f:
        assert f.read() == b"PNGDATA"

    wf = captured["workflow"]
    assert wf["4"]["inputs"]["ckpt_name"] == "my-model.safetensors"
    # The quality prefix is always injected ahead of the per-poem prompt (#96).
    assert wf["6"]["inputs"]["text"] == f"{QUALITY_PREFIX}, moonlit shore, 1girl"
    # The baseline negative is always applied, with the per-poem negative after it.
    assert wf["7"]["inputs"]["text"] == f"{BASE_NEGATIVE}, blurry"
    assert wf["3"]["inputs"]["seed"] == 123
    assert wf["3"]["inputs"]["steps"] == 20
    assert wf["5"]["inputs"]["width"] == 640
    assert captured["view_params"]["filename"] == "x.png"


def test_baseline_prompts_injected_when_empty(tmp_path):
    # Even with no per-poem prompts the quality prefix and baseline negative are
    # always present, so every generation gets the stabilising defaults (#96).
    captured = {}
    client = _make_client(tmp_path, captured)
    client.generate(prompt="p", negative="", checkpoint="m.safetensors")
    wf = captured["workflow"]
    assert wf["6"]["inputs"]["text"] == f"{QUALITY_PREFIX}, p"
    assert wf["7"]["inputs"]["text"] == BASE_NEGATIVE
    assert "bad anatomy" in wf["7"]["inputs"]["text"]


def test_no_image_raises(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "abc"})
        if request.url.path == "/history/abc":
            return httpx.Response(200, json={"abc": {"outputs": {}}})
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ComfyUIClient("http://comfyui:8188", http=http, data_dir=tmp_path, poll_interval=0)
    with pytest.raises(RuntimeError):
        client.generate(prompt="p", checkpoint="m.safetensors")


def test_processor_assigns_seed_when_missing(tmp_path):
    captured = {}
    client = _make_client(tmp_path, captured)
    processor = make_comfyui_processor(client, checkpoint="m.safetensors")
    image = Image(prompt="p", negative="", seed=None, width=512, height=512)
    processor(image)
    assert image.seed is not None
    assert captured["workflow"]["3"]["inputs"]["seed"] == image.seed


def test_processor_rerandomizes_seed_each_attempt(tmp_path):
    # A retry must NOT resubmit the same seed: ComfyUI caches an identical
    # workflow and returns empty outputs ("no image"), so a fresh seed is picked
    # every attempt even when the image already carries one.
    captured = {}
    client = _make_client(tmp_path, captured)
    processor = make_comfyui_processor(client, checkpoint="m.safetensors")
    image = Image(prompt="p", negative="", seed=999, width=512, height=512)
    processor(image)
    assert image.seed != 999
    assert captured["workflow"]["3"]["inputs"]["seed"] == image.seed


def test_await_outputs_surfaces_execution_error(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "abc"})
        if request.url.path == "/history/abc":
            return httpx.Response(
                200,
                json={
                    "abc": {
                        "outputs": {},
                        "status": {
                            "status_str": "error",
                            "messages": [
                                [
                                    "execution_error",
                                    {
                                        "node_type": "KSampler",
                                        "exception_message": "CUDA out of memory",
                                    },
                                ]
                            ],
                        },
                    }
                },
            )
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ComfyUIClient("http://comfyui:8188", http=http, data_dir=tmp_path, poll_interval=0)
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        client.generate(prompt="p", checkpoint="m.safetensors")


def test_processor_records_checkpoint(tmp_path):
    # The checkpoint used must be persisted on the Image for provenance.
    client = _make_client(tmp_path, {})
    processor = make_comfyui_processor(client, checkpoint="AnythingXL_v50.safetensors")
    image = Image(prompt="p", negative="", seed=123, width=512, height=512)
    processor(image)
    assert image.checkpoint == "AnythingXL_v50.safetensors"


def test_processor_uses_sdxl_workflow_and_1024_for_sdxl_model(tmp_path):
    # A per-request SDXL model (image.checkpoint) must drive the SDXL workflow
    # and 1024px — not the 512 default that image.width carries.
    captured = {}
    client = _make_client(tmp_path, captured)
    processor = make_comfyui_processor(client, env={})
    image = Image(
        prompt="p",
        negative="",
        seed=1,
        width=512,
        height=512,
        checkpoint="AnythingXL_v50.safetensors",
    )
    processor(image)
    wf = captured["workflow"]
    assert wf["3"]["inputs"]["sampler_name"] == "dpmpp_2m"  # SDXL sampler
    assert wf["5"]["inputs"]["width"] == 1024
    assert wf["4"]["inputs"]["ckpt_name"] == "AnythingXL_v50.safetensors"
    assert image.width == 1024 and image.height == 1024  # recorded on the image


def test_processor_uses_sd15_512_for_sd15_model(tmp_path):
    captured = {}
    client = _make_client(tmp_path, captured)
    processor = make_comfyui_processor(client, env={})
    image = Image(
        prompt="p",
        negative="",
        seed=1,
        width=512,
        height=512,
        checkpoint="anything-v5.safetensors",
    )
    processor(image)
    wf = captured["workflow"]
    assert wf["3"]["inputs"]["sampler_name"] == "euler_ancestral"  # SD1.5 sampler
    assert wf["5"]["inputs"]["width"] == 512
