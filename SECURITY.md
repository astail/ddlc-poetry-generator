# セキュリティポリシー

## 脆弱性の報告

セキュリティ上の問題を見つけた場合は、**公開 issue を作らず**、GitHub の
[Private vulnerability reporting](https://github.com/astail/ddlc-poetry-generator/security/advisories/new)
（リポジトリの **Security → Report a vulnerability**）から報告してください。

- 初回応答の目安: 数日以内（非公式・ベストエフォート）。
- 対象: 本リポジトリのソースコード（`api` / `frontend` / `worker` / compose・Docker 定義）。
- 対象外: 同梱しない第三者コンポーネント（Claude API・ComfyUI・モデル重み・VOICEVOX 等）
  自体の脆弱性は、それぞれの提供元へ報告してください。詳細は [DISCLAIMER.md](./DISCLAIMER.md) 参照。

## 秘密情報の取り扱い

- `.env`（`ANTHROPIC_API_KEY` / `POSTGRES_PASSWORD` / `REDIS_PASSWORD` / `API_AUTH_TOKEN` 等）は
  **コミットしない**（`.gitignore` 済）。誤って含めた場合は鍵をローテーションのうえ履歴からも除去する。
- 本番相当では `POSTGRES_PASSWORD` / `REDIS_PASSWORD` を強いランダム値にする（compose は空だと fail-fast）。
- 認証・ネットワーク分離の設計は README「認証（API_AUTH_TOKEN）とブラウザ UI」節および
  [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) を参照。

## 対応バージョン

最新の `main` のみをサポート対象とします（非公式ファン制作物のため）。
