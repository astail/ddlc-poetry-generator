# comfyui — Stable Diffusion assets

ComfyUI 用のモデル取得手順とワークフロー定義（M2）。GTX 1060 6GB 向けに **SD 1.5 アニメ調**を前提とします。

> モデル重みはリポジトリに含めません。利用するチェックポイントの**ライセンスを必ず確認**してください（多くは CreativeML OpenRAIL-M）。[../DISCLAIMER.md](../DISCLAIMER.md) 参照。

## モデルの取得

```bash
./comfyui/download_models.sh
# 別モデルを使う場合:
SD_MODEL_URL=https://.../model.safetensors SD_CHECKPOINT=mymodel.safetensors \
  ./comfyui/download_models.sh
```

- 取得先: `./models/comfyui/checkpoints/<SD_CHECKPOINT>`
- このディレクトリは `comfyui` サービスに `/models` としてマウントされます（[../docker-compose.yml](../docker-compose.yml)）。
- 使ったファイル名は `.env` の `SD_CHECKPOINT` に設定してください。

## ワークフロー

`workflows/poem_sd15.json` は ComfyUI の **API フォーマット**（txt2img）です。
ノード構成: CheckpointLoaderSimple → CLIPTextEncode(pos/neg) → EmptyLatentImage →
KSampler → VAEDecode → SaveImage。

画像生成パイプライン（#12）は、このテンプレートに以下を差し込んで ComfyUI に投入します。

| プレースホルダ | 差し込み元 |
|---|---|
| `4.inputs.ckpt_name` | `SD_CHECKPOINT`（.env） |
| `6.inputs.text` | 詩から生成した `image_prompt` |
| `7.inputs.text` | `image_negative`（既定のネガティブも含む） |
| `3.inputs.seed` / `steps` / `cfg` | seed / `SD_STEPS` / `SD_CFG` |
| `5.inputs.width` / `height` | `SD_WIDTH` / `SD_HEIGHT`（既定 512） |

## GTX 1060 6GB メモ
- 512×512、SD1.5 で 1枚あたり概ね 5〜15 秒。
- VRAM が厳しい場合は ComfyUI を `--lowvram`/`--normalvram` で起動（#10 で設定済）。
- 実際の起動（ComfyUI サービス）と生成は #10 / #12 で実施します。

## SDXL（任意, #22）

`.env` で `SD_MODEL_TYPE=sdxl` にすると、ワーカーは SDXL 用ワークフロー
（`workflows/poem_sdxl.json` 相当：1024px・dpmpp_2m/karras・steps 30）を使います。

- モデル取得（単一ファイルの SDXL チェックポイント）:
  ```bash
  SD_MODEL_URL=https://.../sdxl_model.safetensors SD_CHECKPOINT=sdxl.safetensors \
    ./comfyui/download_models.sh
  ```
  `.env` の `SD_CHECKPOINT=sdxl.safetensors` に合わせます。
- **6GB offload**: ComfyUI は `--lowvram` で起動済（重みを CPU/GPU 間でオフロード）。
  GTX 1060 6GB でも生成できますが SD1.5 より大幅に低速です。`SD_WIDTH/HEIGHT` を
  768〜1024 に調整して VRAM/速度を加減してください。
- 生成パイプライン（`ComfyUIClient` / `workflow_for`）は SD1.5 と同一で、ワークフローと
  解像度のみ切替わります（#12 で実機検証済の経路を再利用）。
