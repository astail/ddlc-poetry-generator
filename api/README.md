# api (FastAPI)

オーケストレーション層。Claude API で詩を生成し、画像/音声ジョブを Redis に投入、
生成物メタデータを PostgreSQL に保存、フロントへ SSE で進捗を配信する。

主なエンドポイント（予定）:
- `POST /api/generate`
- `GET  /api/poems` / `GET /api/poems/{id}`
- `GET  /api/poems/{id}/status` (SSE)
- `GET  /api/assets/...`
- `GET  /api/models`（選択可能な画像モデル）
- `GET  /api/tts/capabilities`（TTS バックエンドと音声化できる言語。フロントが ja 音声の可否判定に使用 / #89）

実装は M1 の issue を参照。
