import json

import httpx

from app.comfyui_client import (
    DEFAULT_WORKFLOW,
    SDXL_WORKFLOW,
    ComfyUIClient,
    workflow_for,
)


def test_workflow_for_selects_sdxl():
    assert workflow_for("sdxl") is SDXL_WORKFLOW
    assert workflow_for("SDXL") is SDXL_WORKFLOW
    assert workflow_for("sd15") is DEFAULT_WORKFLOW
    assert workflow_for("") is DEFAULT_WORKFLOW
    # SDXL defaults differ from SD1.5
    assert SDXL_WORKFLOW["3"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert SDXL_WORKFLOW["5"]["inputs"]["width"] == 1024
    assert DEFAULT_WORKFLOW["3"]["inputs"]["sampler_name"] == "euler_ancestral"
    assert DEFAULT_WORKFLOW["5"]["inputs"]["width"] == 512


def test_generate_uses_sdxl_workflow(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/prompt":
            captured["wf"] = json.loads(request.content)["prompt"]
            return httpx.Response(200, json={"prompt_id": "x"})
        if path == "/history/x":
            return httpx.Response(
                200,
                json={
                    "x": {
                        "outputs": {
                            "9": {
                                "images": [{"filename": "a.png", "subfolder": "", "type": "output"}]
                            }
                        }
                    }
                },
            )
        if path == "/view":
            return httpx.Response(200, content=b"PNGDATA")
        return httpx.Response(404)

    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = ComfyUIClient(
        "http://comfyui:8188",
        http=http,
        data_dir=tmp_path,
        workflow=SDXL_WORKFLOW,
        poll_interval=0,
    )
    client.generate(
        prompt="p",
        checkpoint="sdxl.safetensors",
        seed=1,
        steps=30,
        cfg=7,
        width=1024,
        height=1024,
    )
    wf = captured["wf"]
    assert wf["3"]["inputs"]["sampler_name"] == "dpmpp_2m"
    assert wf["3"]["inputs"]["scheduler"] == "karras"
    assert wf["5"]["inputs"]["width"] == 1024
    assert wf["4"]["inputs"]["ckpt_name"] == "sdxl.safetensors"
