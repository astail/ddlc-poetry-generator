# api (FastAPI)

オーケストレーション層。Claude API で詩を生成し、画像/音声ジョブを Redis に投入、
生成物メタデータを PostgreSQL に保存、フロントへ SSE で進捗を配信する。

主なエンドポイント（予定）:
- `POST /api/generate`
- `GET  /api/poems` / `GET /api/poems/{id}`
- `GET  /api/poems/{id}/status` (SSE)
- `GET  /api/assets/...`

実装は M1 の issue を参照。
