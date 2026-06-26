# worker-gpu

画像生成ジョブのワーカー。Redis の `jobs:image` リストからジョブIDを取り出し、
`jobs`/`images` の状態を更新する（queued→running→done/failed）。失敗時はエラーを記録。

- 実装は共有 `app` パッケージ（`app/worker_gpu.py`）にあり、**api イメージを再利用**して起動します。
  compose では `worker-gpu` サービスが `build: ./api` + `command: python -m app.worker_gpu`。
- 実際の Stable Diffusion 生成は `processor` として注入します（#12 で ComfyUI 連携を実装）。
  既定の processor は未実装例外を投げます。
- GPU は `comfyui` サービスが占有するため、このワーカー自体は GPU を直接持ちません。
