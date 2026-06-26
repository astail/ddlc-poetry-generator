# worker-gpu (Python)

画像生成ジョブのワーカー。Redis から image ジョブを取り出し、ComfyUI の HTTP API を
呼んで Stable Diffusion で画像を生成、`/data` に保存して `images` を更新する。

- GPU は `comfyui` サービスが占有するため、このワーカー自体は GPU を直接持たない。
- 既定モデルは SD 1.5 アニメ調（GTX 1060 6GB 向け、512px）。
- モデル重みはリポジトリに含めない（取得手順は M2 の issue）。
