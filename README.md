# DDLC Poetry Generator

DDLC の4人（**Sayori / Natsuki / Yuri / Monika**）の作風で詩を **自動生成**し、
その詩から **画像** と **読み上げ音声** を作って Web で鑑賞できる、非公式ファン制作プロジェクトです。

- 📝 **詩生成**: Claude API（キャラ別 persona、英語生成＋日本語訳）
- 🎨 **画像生成**: Stable Diffusion / ComfyUI（GTX 1060 6GB 向けに SD 1.5・`--lowvram`）
- 🔊 **読み上げ**: 英語=Piper（CPU・キャラ別ボイス）/ XTTS（GPU・任意）、日本語=VOICEVOX（アニメ調キャラボイス・既定で有効）
- 🐳 `docker compose up` で一式起動（api / frontend / 2 workers / comfyui / voicevox / postgres / redis）

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
#    DB マイグレーションは migrate サービスが起動時に自動実行します
#    （api / worker はその完了を待ってから起動するため、初回リクエストでも
#     テーブルが揃っています）。手動で流す必要はありません。
docker compose up -d --build

# 4) ブラウザで開く
#    フロント:   http://localhost:3000
#    API ドキュメント: http://localhost:8000/docs
```

> マイグレーションを手動で流したい場合（再実行や確認用）:
> `docker compose run --rm migrate`（または `docker compose run --rm api alembic upgrade head`）。
> 初期マイグレーション（`0001_initial`）は `now()` を `server_default` に使う **Postgres 前提**です（本スタックの DB は PostgreSQL）。

キャラとお題を選んで **Generate** すると、詩がすぐ表示され、画像と音声が後追いで埋まります。
過去の生成物は **Gallery**（`/gallery`）から再閲覧できます。

> 読み上げ用の Piper ボイスは初回利用時に `/data/voices` へ自動ダウンロードされます（非同梱）。

## アーキテクチャ（概要）

```
frontend (Next.js) ─▶ api (FastAPI, Claude) ─▶ redis ─▶ worker-gpu ─▶ comfyui (SD, GPU)
                              │                       └▶ worker-tts (en=Piper/XTTS, ja=VOICEVOX)
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
| `REDIS_PASSWORD` | — | **必須・要変更**。既定値なし。未設定だと compose が起動失敗（fail-fast）。Redis は `--requirepass` 付きで起動 |
| `REDIS_URL` | （compose が自動生成） | ジョブキュー。`REDIS_PASSWORD` から組み立てられ `.env` には書かない。非 compose / 外部 Redis 利用時のみ上書き |
| `COMFYUI_URL` | `http://comfyui:8188` | ComfyUI API |
| `SD_CHECKPOINT` | `anything-v5.safetensors` | 既定の SD チェックポイント名（取得物に合わせる） |
| `SD_MODELS` | （組込のみ） | 選択可能モデルの許可リスト拡張。`name:type[:label]` のカンマ区切り。UI のドロップダウン（`GET /api/models`）と `POST /api/generate` の `model` に対応。`AnythingXL_v50.safetensors`（SDXL）等を `models/comfyui/checkpoints/` に配置して指定 |
| `SD_WIDTH` / `SD_HEIGHT` / `SD_STEPS` / `SD_CFG` | 512 / 512 / 25 / 7 | 画像生成設定（SDXL は 1024/1024/30 が既定） |
| `TTS_BACKEND` | `piper` | **英語**の読み上げバックエンド。`piper`（CPU・英語のみ）/ `xtts`（GPU・多言語）。日本語は `VOICEVOX_URL` 側で対応 |
| `VOICEVOX_URL` | `http://voicevox:50021` | **日本語(`lang=ja`)** の読み上げに使う VOICEVOX エンジンの URL。`voicevox` サービスは既定スタックに含まれ `docker compose up` で自動起動するため、日本語音声は **既定で有効**。無効化するにはこの値を空にする（その間はフロントが `GET /api/tts/capabilities` を見て「音声を生成（日本語）」を無効化する / #89） |
| `RATE_LIMIT_PER_MIN` | `20` | `POST /api/generate` のIP毎レート上限 |
| `API_AUTH_TOKEN` | —（空=無認証） | 設定すると `POST /api/generate`・`DELETE /api/poems/{id}`・`GET /api/stats` が `X-API-Key: <token>` を要求（定数時間比較）。**同梱ブラウザ UI とは併用不可** — 下記「[認証とブラウザ UI](#認証api_auth_tokenとブラウザ-ui)」参照 |
| `JOB_MAX_RETRIES` | `1` | ジョブ失敗時の再投入回数（超過でデッドレター） |
| `DATA_DIR` | `/data` | 生成物の保存先（ボリューム） |

## 認証（API_AUTH_TOKEN）とブラウザ UI

`API_AUTH_TOKEN` を設定すると、`POST /api/generate` / `DELETE /api/poems/{id}` / `GET /api/stats` は
`X-API-Key: <token>` ヘッダ（定数時間比較）を要求します。未設定なら無認証で、ローカル / LAN 自ホスト向けの既定動作です。

> [!IMPORTANT]
> **同梱のブラウザ UI（`frontend`）は `X-API-Key` を送信しません。** 加えて `NEXT_PUBLIC_*` は
> ブラウザバンドルに焼き込まれる**公開値**なので、鍵をフロントに安全に埋め込むこともできません。
> そのため `API_AUTH_TOKEN` を有効化すると、UI からの生成・削除は **401** になります。
> 認証は「UI を使わない構成」または「前段プロキシで鍵を注入する構成」で使ってください。

### 使い分け

- **自ホスト（既定・推奨）**: `API_AUTH_TOKEN` は未設定のまま、`api` をインターネットに公開せず LAN 内に留める。
  外部サイトからのブラウザ経由アクセスは CORS（既定で loopback + private-LAN のみ許可）で防ぐ。生成の乱用や
  削除は レート制限（`RATE_LIMIT_PER_MIN`）と同時実行上限（`GENERATE_MAX_CONCURRENCY`）で抑制する。
- **ヘッドレス / 外部クライアント**: UI を使わず API を直接叩く用途に限り `API_AUTH_TOKEN` を設定し、
  クライアント側が `X-API-Key` を付与する。
- **UI を公開しつつ保護したい**: フロントの前段にリバースプロキシ（BFF）を置き、そこで `X-API-Key` を注入する。
  鍵はサーバ側にのみ置き、ブラウザには一切出さない。

  ```nginx
  # 例: nginx。ブラウザには鍵を出さず、プロキシが API リクエストに付与する。
  # $api_key はサーバ側の環境変数などから供給する（ブラウザには露出しない）。
  location /api/ {
    proxy_pass http://api:8000;
    proxy_set_header X-API-Key $api_key;
  }
  ```

  この構成では `NEXT_PUBLIC_API_BASE` をプロキシ経由の同一オリジンに向け、ブラウザは鍵を扱わない。

> 将来的に UI 自体へログイン（サーバ側 secret による軽量セッション）を導入する場合は別 issue で扱う。

## テスト

本番 API イメージには dev 依存（pytest/ruff）やテストを同梱しないため、テストは
ホスト側（ピン留め済みの dev 依存）で実行します:

```bash
# ユニットテスト（GPU/ネットワーク不要）
pip install -r api/requirements-dev.txt && pip install --no-deps ./api
cd api && python -m pytest

# lint / format
cd api && ruff check . && ruff format --check .
```

CI（GitHub Actions）では `docker compose config` 検証・`ruff`/`pytest`・フロントの型/build/lint・api/frontend イメージのビルド・依存監査を実行します。

### 依存の固定（再現性）

ビルドを再現可能にするため依存をロックしています。更新時は再生成してコミットしてください:

- **Python（api）**: 本番（runtime）と dev で 2 つに分離。
  - `cd api && uv pip compile pyproject.toml -o requirements.txt`（本番イメージ用・dev 無し）
  - `cd api && uv pip compile pyproject.toml --extra dev -o requirements-dev.txt`（テスト/CI 用）
- **フロント**: `cd frontend && npm install`（`package-lock.json` を更新）。Dockerfile / CI は `npm ci` でロック基準にインストール。
- **ComfyUI**: `comfyui/Dockerfile` の `COMFYUI_VERSION`（リリースタグ）を更新。

> コンテナは非 root ユーザで実行します（#55）。`api`/`worker` は `/data`（名前付き
> ボリューム）へ書き込むため、**初回作成時**に非 root の所有権が引き継がれます。
> 既存の root 所有ボリュームをアップグレードする場合は、一度
> `docker compose down -v` で作り直すか、ボリュームを当該 UID(10001) に chown して
> ください。

## トラブルシュート

- **画像が `failed` / ComfyUI が起動しない**
  - `nvidia-container-toolkit` が入っているか: `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`
  - GPU 認識確認（:8188 はホスト非公開のためコンテナ内から）: `docker compose exec comfyui python -c "import urllib.request,sys; sys.stdout.write(urllib.request.urlopen('http://localhost:8188/system_stats').read().decode())"`（`cuda` デバイスが出るか）
  - VRAM 不足: ComfyUI は `--lowvram` 起動。`SD_WIDTH/HEIGHT` を下げる
  - チェックポイント未配置: `./comfyui/download_models.sh` を実行し、`SD_CHECKPOINT` を一致させる
- **API が 500 / テーブルが無い**: 通常は `migrate` サービスが起動時に自動適用しますが、失敗した場合は `docker compose logs migrate` を確認し、`docker compose run --rm migrate`（= `alembic upgrade head`）を再実行
- **音声が `failed`**: 初回はボイス DL に時間がかかる。ネットワークと `/data/voices` を確認
- **`POST /api/generate` が 429**: レート制限。`RATE_LIMIT_PER_MIN` を調整
- **フロントから API に繋がらない**: `NEXT_PUBLIC_API_BASE`（既定 `http://localhost:8000`）を確認

## ライセンス

ソースコードは [MIT](./LICENSE)。第三者IP・モデル・APIの権利は [DISCLAIMER.md](./DISCLAIMER.md) を参照。
