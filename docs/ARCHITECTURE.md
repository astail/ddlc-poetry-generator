# ARCHITECTURE — DDLC Poetry Generator

## コンテナ構成

| service | 役割 | GPU | 言語/技術 |
|---|---|---|---|
| `frontend` | UI（詩・画像・音声の表示/再生） | – | Next.js + TS + Tailwind |
| `api` | オーケストレーション、Claude 呼び出し、ジョブ投入 | – | FastAPI (Python) |
| `db` | 生成物メタデータ | – | PostgreSQL |
| `redis` | ジョブキュー / ブローカー | – | Redis |
| `comfyui` | Stable Diffusion 実行（HTTP API） | ✅ 占有 | ComfyUI |
| `worker-gpu` | 画像ジョブ消費 → ComfyUI 呼び出し → 保存 | – | Python（自前の Redis list キュー） |
| `worker-tts` | 音声ジョブ消費 → Piper(CPU)/XTTS(GPU) → 保存 | △ 任意 | Python（自前の Redis list キュー） |

> 画像生成の重い処理は `comfyui` に集約し、GPU の占有点を1つにする。`worker-gpu` は
> ComfyUI の API を叩くだけなので GPU を直接持たない。XTTS を使う場合のみ `worker-tts`
> に GPU を割り当て、画像生成とは逐次化して 6GB に収める。

## GPU / VRAM 設計（GTX 1060 6GB）

- 既定: **ComfyUI(SD1.5, 512px) のみ GPU 常駐**（normalvram で ~3–4GB）。
  読み上げは **Piper(CPU)** → VRAM 競合なし。
- XTTS を有効化する場合: SD と XTTS を同時常駐させず、ジョブ単位で逐次実行
  （`TTS_BACKEND=xtts` 時はキューの並行度を制御）。
- compose の GPU 割当（抜粋）:
  ```yaml
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
  ```
  ホスト側に nvidia-container-toolkit が必要。

## 処理フロー

```
[frontend] POST /api/generate (character, theme)
     │
[api] ── Claude 1コール ──▶ {poem_en, poem_ja, image_prompt, image_negative, voice_hints}
     │  └─ poems を DB 保存、詩を即レスポンス
     │  └─ image ジョブ / audio ジョブを redis に投入
     │
[worker-gpu] image ジョブ ─▶ ComfyUI(SD) ─▶ /data に画像保存 ─▶ images 更新
[worker-tts] audio ジョブ ─▶ Piper/XTTS   ─▶ /data に音声保存 ─▶ audios 更新
     │
[frontend] GET /api/poems/{id} を約2秒間隔でポーリングして進捗確認し、絵・声が揃い次第表示
```

## ストレージ

- 生成画像・音声は名前付きボリューム `/data`（`DATA_DIR`）に保存。
- メタデータ（パス・seed・状態）は PostgreSQL。
- リポジトリには重み・生成物を含めない。

## ネットワーク / ポート

- `frontend` :3000（公開）
- `api` :8000（frontend からアクセス、必要に応じて公開）
- `comfyui` :8188 / `db` :5432 / `redis` :6379 は内部ネットワークのみ

## 障害・運用

- ジョブは `jobs` テーブルで状態管理（queued/running/done/failed）。失敗時リトライ。
- Claude / ComfyUI 呼び出しはタイムアウト＋指数バックオフ。
- レート制限（M4）で API 乱用と GPU 飽和を抑制。
