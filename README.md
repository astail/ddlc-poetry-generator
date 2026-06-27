# DDLC Poetry Generator

DDLC の4人（**Sayori / Natsuki / Yuri / Monika**）の作風で詩を **自動生成**し、
その詩から **画像** と **読み上げ音声** を作って Web で鑑賞できる、非公式ファン制作プロジェクトです。

- 📝 **詩生成**: Claude API（キャラ別 persona、英語生成＋日本語訳）
- 🎨 **画像生成**: Stable Diffusion / ComfyUI（GTX 1060 6GB 向けに SD 1.5・`--lowvram`）
- 🔊 **読み上げ**: Piper（CPU・キャラ別ボイス）/ XTTS（GPU・任意）
- 🐳 `docker compose up` で一式起動（api / frontend / 2 workers / comfyui / postgres / redis）

> [!IMPORTANT]
> 本プロジェクトは **非公式・非商用のファン制作物**です。Team Salvato とは無関係で、
> 公式アセットは一切同梱しません。詳細は [DISCLAIMER.md](./DISCLAIMER.md) を必ずお読みください。

## 必要環境

- Docker / Docker Compose v2+
- NVIDIA GPU（GTX 1060 6GB 以上）+ ドライバ + **nvidia-container-toolkit**（画像生成に必要）
- Anthropic API キー

## クイックスタート

```bash
# 1) 設定
cp .env.example .env
#    .env を編集し、最低限 ANTHROPIC_API_KEY を設定する

# 2) 画像生成用の SD1.5 チェックポイントを取得（重みは非同梱）
#    既定の取得先を使う場合:
./comfyui/download_models.sh
#    別モデルを使う場合（ライセンス確認のこと）:
#    SD_MODEL_URL=https://.../model.safetensors SD_CHECKPOINT=mymodel.safetensors ./comfyui/download_models.sh
#    → .env の SD_CHECKPOINT を、取得したファイル名に合わせて設定する

# 3) 起動（初回はイメージビルド + ComfyUI のベースイメージ取得で時間がかかります）
docker compose up -d --build

# 4) DB マイグレーション（初回のみ）
docker compose run --rm api alembic upgrade head

# 5) ブラウザで開く
#    フロント:   http://localhost:3000
#    API ドキュメント: http://localhost:8000/docs
```

キャラとお題を選んで **Generate** すると、詩がすぐ表示され、画像と音声が後追いで埋まります。
過去の生成物は **Gallery**（`/gallery`）から再閲覧できます。

> 読み上げ用の Piper ボイスは初回利用時に `/data/voices` へ自動ダウンロードされます（非同梱）。

## アーキテクチャ（概要）

```
frontend (Next.js) ─▶ api (FastAPI, Claude) ─▶ redis ─▶ worker-gpu ─▶ comfyui (SD, GPU)
                              │                       └▶ worker-tts (Piper/XTTS)
                              └▶ postgres            (生成物は /data ボリューム)
```

GTX 1060 は 6GB のため、画像生成のみ GPU を占有し、既定の読み上げは CPU(Piper) に分離しています。
詳細は [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) / [docs/SPEC.md](./docs/SPEC.md) を参照。

## 環境変数リファレンス（`.env`）

| 変数 | 既定 | 説明 |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | **必須**。Claude API キー |
| `POEM_MODEL` | `claude-sonnet-4-6` | 詩生成モデル |
| `POEM_MAX_TOKENS` / `POEM_TEMPERATURE` | `1500` / `1.0` | 生成パラメータ（temperature は対応モデルのみ） |
| `POSTGRES_USER` / `POSTGRES_DB` | `ddlc` / `ddlc_poems` | Postgres のユーザ / DB 名 |
| `POSTGRES_PASSWORD` | — | **必須・要変更**。既定値なし。未設定だと compose が起動失敗（fail-fast）。**LAN / 公開前に必ず強いランダム値へ** |
| `DATABASE_URL` | （compose が自動生成） | `POSTGRES_*` から組み立てられる。重複防止のため `.env` には書かない。非 compose / 外部 DB 利用時のみ上書き |
| `REDIS_URL` | `redis://redis:6379/0` | ジョブキュー |
| `COMFYUI_URL` | `http://comfyui:8188` | ComfyUI API |
| `SD_CHECKPOINT` | `anything-v5.safetensors` | 使用する SD チェックポイント名（取得物に合わせる） |
| `SD_WIDTH` / `SD_HEIGHT` / `SD_STEPS` / `SD_CFG` | 512 / 512 / 25 / 7 | 画像生成設定 |
| `TTS_BACKEND` | `piper` | `piper`（CPU）/ `xtts`（GPU） |
| `RATE_LIMIT_PER_MIN` | `20` | `POST /api/generate` のIP毎レート上限 |
| `JOB_MAX_RETRIES` | `1` | ジョブ失敗時の再投入回数（超過でデッドレター） |
| `DATA_DIR` | `/data` | 生成物の保存先（ボリューム） |

## テスト

```bash
# ユニットテスト（docker compose 上、GPU/ネットワーク不要）
docker compose run --rm --no-deps api python -m pytest

# lint / format
docker compose run --rm --no-deps api sh -c "ruff check . && ruff format --check ."
```

CI（GitHub Actions）でも `docker compose config` 検証と `ruff` + `pytest` を実行します。

## トラブルシュート

- **画像が `failed` / ComfyUI が起動しない**
  - `nvidia-container-toolkit` が入っているか: `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`
  - GPU 認識確認（:8188 はホスト非公開のためコンテナ内から）: `docker compose exec comfyui python -c "import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://localhost:8188/system_stats').read().decode())"`（`cuda` デバイスが出るか）
  - VRAM 不足: ComfyUI は `--lowvram` 起動。`SD_WIDTH/HEIGHT` を下げる
  - チェックポイント未配置: `./comfyui/download_models.sh` を実行し、`SD_CHECKPOINT` を一致させる
- **API が 500 / テーブルが無い**: `docker compose run --rm api alembic upgrade head` を実行
- **音声が `failed`**: 初回はボイス DL に時間がかかる。ネットワークと `/data/voices` を確認
- **`POST /api/generate` が 429**: レート制限。`RATE_LIMIT_PER_MIN` を調整
- **フロントから API に繋がらない**: `NEXT_PUBLIC_API_BASE`（既定 `http://localhost:8000`）を確認

## ライセンス

ソースコードは [MIT](./LICENSE)。第三者IP・モデル・APIの権利は [DISCLAIMER.md](./DISCLAIMER.md) を参照。
