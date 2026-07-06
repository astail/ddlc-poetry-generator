# Changelog

本プロジェクトの主要な変更点を記録する。書式は [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/)、
バージョンは [Semantic Versioning](https://semver.org/lang/ja/) に従う（1.0 未満のため破壊的変更も MINOR で入りうる）。

## [Unreleased]

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
