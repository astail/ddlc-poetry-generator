# API リファレンス — DDLC Poetry Generator

`api`（FastAPI）が提供する HTTP API。対話的な OpenAPI ドキュメントは起動後 `http://localhost:8000/docs`。

- ベース URL: `http://<host>:8000`（既定ポート `API_PORT=8000`）
- 本文は JSON（`Content-Type: application/json`）
- 生成物（画像/音声）は `GET /api/assets/...` で配信

## 横断的な仕様

### 認証
`API_AUTH_TOKEN` が設定されている場合、`POST /api/generate` / `DELETE /api/poems/{id}` / `GET /api/stats` は
リクエストヘッダ `X-API-Key: <token>`（定数時間比較）を要求し、欠落/不一致は **401**。未設定なら無認証。
ブラウザ UI との併用制約は README「認証（API_AUTH_TOKEN）とブラウザ UI」節を参照。

### CORS
`CORS_ALLOW_ORIGINS`（カンマ区切り、`*` で全許可）で明示指定。未設定時は loopback + private-LAN(RFC1918)
オリジンのみ許可（自ホスト向け）。資格情報（Cookie）は使わない（認証はヘッダ）。

### レート制限
`POST /api/generate` は IP 毎 `RATE_LIMIT_PER_MIN`（既定 20/分）。超過は **429**（`Retry-After` ヘッダ付き）。
`REDIS_URL` 設定時は全プロセス/レプリカで共有（#135）。

### 相関 ID / セキュリティヘッダ
すべてのレスポンスに `X-Request-ID`（受領した値をエコー、無ければ生成）と `X-Content-Type-Options: nosniff` が付く。

### エラー形式
FastAPI 既定の `{"detail": "..."}`（バリデーションエラーは `detail` が配列）。主なコード:
`401`（認証）/ `404`（未検出）/ `422`（入力検証）/ `429`（レート）/ `503`（生成混雑・依存不達）/ `502`（詩生成失敗）。

---

## エンドポイント

### `GET /health`
DB + Redis 到達確認（readiness）。到達不能なら **503**。

```json
200 { "status": "ok", "db": "ok", "redis": "ok" }
503 { "status": "degraded", "db": "ok", "redis": "error" }
```

### `POST /api/generate`
詩を生成して即返し、画像/音声ジョブを投入する。**認証・レート制限・同時実行上限**の対象。

リクエスト:

| フィールド | 型 | 既定 | 説明 |
|---|---|---|---|
| `character` | string | — | **必須**。`sayori` / `natsuki` / `yuri` / `monika` |
| `theme` | string \| null | `null` | お題（最大 200 文字） |
| `lang` | string | `en` | `en` または `ja` |
| `generate_image` | bool | `true` | 画像生成の要否 |
| `generate_audio` | bool | `true` | 音声生成の要否 |
| `model` | string \| null | `null` | 画像モデル名（`GET /api/models` の許可リスト。未知は 422） |
| `image_prompt_extra` | string \| null | `null` | 追加の positive プロンプト（最大 500 文字。`generate_image=false` 時は無視） |

```bash
curl -X POST http://localhost:8000/api/generate \
  -H 'Content-Type: application/json' \
  -d '{"character":"yuri","theme":"midnight sea","lang":"en"}'
```

レスポンス `200`（`PoemDetail`）。画像/音声は生成直後 `pending`/`queued` で、`GET /api/poems/{id}` のポーリングで
`status` が `done`/`failed` になるのを待つ（下記「ポーリング契約」）。

- `401` 認証必要 / `422` 入力不正・未知モデル / `429` レート超過 / `503` 生成混雑（`GENERATE_MAX_CONCURRENCY` 超過）/ `502` 詩生成失敗

### `GET /api/poems`
一覧（新しい順）。

| クエリ | 型 | 既定 | 範囲 |
|---|---|---|---|
| `limit` | int | 20 | 1–100 |
| `offset` | int | 0 | ≥0 |
| `character` | string | — | 任意（4キャラのいずれか） |

レスポンス `200`: `PoemSummary[]`。

### `GET /api/poems/{poem_id}`
詳細。`200` = `PoemDetail` / `404` = 未検出。フロントはこれを **約 2 秒間隔でポーリング**して進捗を見る。

### `DELETE /api/poems/{poem_id}`
詩と生成物（画像/音声ファイル・ジョブ）を削除。**認証対象**。`204` = 成功 / `404` = 未検出。

### `GET /api/models`
選択可能な画像生成モデル一覧（フロントのドロップダウン用）。

```json
{ "default": "anything-v5.safetensors",
  "models": [ { "name": "anything-v5.safetensors", "label": "Anything v5 (SD 1.5)", "type": "sd15" } ] }
```

### `GET /api/tts/capabilities`
読み上げバックエンドと対応言語。フロントは日本語不可時に「音声を生成」を無効化する（#89）。

```json
{ "backend": "piper", "voicevox": true, "langs": ["en", "ja"] }
```

### `GET /api/stats`
集計（総詩数・キャラ別・アセット状態）。**認証対象**（鍵設定時）。

```json
{ "total_poems": 42, "by_character": {"yuri": 10}, "images": {"done": 30}, "audios": {"done": 28} }
```

### `GET /api/assets/{path}`
生成物（`images/<name>` / `audio/<name>`）の配信。`data_dir` 配下に限定（パストラバーサル防止）。`404` = 未検出。

---

## レスポンススキーマ

**PoemSummary**: `id, character, title, title_ja?, mood?, lang, created_at, image_status?, audio_status?, image_url?, audio_url?`

**PoemDetail**（Summary を拡張）: `+ theme?, model?, poem_en, poem_ja, images[ImageOut], audios[AudioOut]`

**ImageOut**: `id, status, path?, url?, width, height, seed?, checkpoint?`

**AudioOut**: `id, backend, lang, status, path?, url?, voice?`

`status` は `pending` / `running` / `done` / `failed`。`*_url` は `GET /api/assets/...` への相対パス。

## ポーリング契約

1. `POST /api/generate` → 詩（テキスト）は即返る。`images[].status` / `audios[].status` は `pending`。
2. クライアントは `GET /api/poems/{id}` を **約 2 秒間隔**で取得し、各アセットが `done`（`url` 有効）または `failed` に
   なるまで繰り返す（SSE は非採用・簡略化のため。docs/SPEC.md §7）。
3. `done` になったら `url` を `GET /api/assets/...` で取得して表示/再生する。
