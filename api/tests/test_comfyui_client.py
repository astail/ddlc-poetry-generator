import json

import httpx
import pytest

from app.comfyui_client import ComfyUIClient, make_comfyui_processor
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
                                "images": [
                                    {"filename": "x.png", "subfolder": "", "type": "output"}
                                ]
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
    return ComfyUIClient(
        "http://comfyui:8188", http=http, data_dir=tmp_path, poll_interval=0
    )


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
    assert wf["6"]["inputs"]["text"] == "moonlit shore, 1girl"
    assert wf["7"]["inputs"]["text"] == "blurry"
    assert wf["3"]["inputs"]["seed"] == 123
    assert wf["3"]["inputs"]["steps"] == 20
    assert wf["5"]["inputs"]["width"] == 640
    assert captured["view_params"]["filename"] == "x.png"


def test_default_negative_used_when_empty(tmp_path):
    captured = {}
    client = _make_client(tmp_path, captured)
    client.generate(prompt="p", negative="", checkpoint="m.safetensors")
    assert "bad anatomy" in captured["workflow"]["7"]["inputs"]["text"]


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
