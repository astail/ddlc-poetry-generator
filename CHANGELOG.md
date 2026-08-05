# Changelog

本プロジェクトの主要な変更点を記録する。書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う（1.0 未満のため破壊的変更も MINOR で入りうる）。

## [Unreleased]

### Added
- レート制限を **名前** 単位で設定できる `RATE_LIMIT_CLIENTS`（`frontend=120,cloudflared,10.8.0.0/24=5`）。
  docker compose のサービス名 / ホスト名は実行時に DNS 解決（30 秒キャッシュ）するので、
  コンテナの IP が変わっても追従する。未設定なら従来どおり接続元 IP 単位。
- frontend が `/api/*` を compose のサービス名 `api` へリバースプロキシ（`API_ORIGIN`、既定
  `http://api:8000`）。ブラウザから見て同一オリジンになるため CORS も API のポート公開も不要。
- api のホスト側 bind アドレスを選べる `API_BIND`（既定 `127.0.0.1`）。

### Changed
- **破壊的**: api のポートは既定でループバックのみに bind するようになった。LAN の別端末や
  外部クライアントから API を直接叩いている場合は `.env` に `API_BIND=0.0.0.0` を設定する
  （ブラウザ UI は frontend 経由になるため設定不要）。
- **破壊的**: ブラウザの API 呼び出し先が同一オリジンの `/api/*` になった。`NEXT_PUBLIC_API_BASE`
  は「プロキシを迂回して別オリジンを叩く」ときだけの設定になり、`NEXT_PUBLIC_API_PORT` は廃止。
- CORS の既定許可に「名前」のオリジンを追加（`http://frontend:3000` のようなドット無しホスト名、
  `.local` / `.internal` / `.lan` / `.home.arpa`）。IP リテラルを書かなくても LAN のホスト名で通る。
- Cloudflare Tunnel の public hostname は 1 本（→ `http://frontend:3000`）で済むようになった。

## [0.1.0] - 2026-07-06

初回リリース。DDLC 4 キャラの作風で詩を生成し、画像（Stable Diffusion / ComfyUI）と
読み上げ音声（Piper / XTTS / VOICEVOX）を作って Web で鑑賞する `docker compose` 一式。

### Added
- 詩生成（Claude・キャラ別 persona・英語生成＋日本語訳）、画像生成、読み上げ（日英）、ギャラリー / 履歴。
- 画像モデル選択、画像 / 音声のオプション化、画像の追加プロンプト。
- 信頼性: at-least-once ジョブキュー（reaper / reconciler / retry / dead-letter）、定期 reconcile、
  生成の同時実行上限、Redis 共有レート制限、ヘルスチェック（api / frontend / worker）。
- セキュリティ: 非 root コンテナ、ネットワーク分離、Redis 認証、CORS 制限、定数時間 API キー比較、
  セキュリティレスポンスヘッダ、compose のシークレット fail-fast。
- DB: 値の CHECK 制約、`jobs` の複合 index、`DATABASE_URL` の fail-fast + `pool_pre_ping`。
- 可観測性: request-id ミドルウェア + 構造化ログ + Sentry opt-in。
- 開発基盤: フロント / バックエンドのテスト（coverage 85% ゲート）、CI、Dependabot、
  docs（ARCHITECTURE / API / 認証 / 環境変数）、コミュニティヘルスファイル。

[Unreleased]: https://github.com/astail/ddlc-poetry-generator/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/astail/ddlc-poetry-generator/releases/tag/v0.1.0
