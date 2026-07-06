# コントリビュートガイド

非公式・非商用のファン制作プロジェクトです。まず [DISCLAIMER.md](./DISCLAIMER.md) を確認してください。

## 開発環境

```bash
cp .env.example .env   # 最低限 ANTHROPIC_API_KEY を設定
docker compose up -d --build
```

全体像は [README.md](./README.md) / [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) を参照。

## テスト / lint（push 前に必須）

**API（Python・GPU/ネットワーク不要）**

```bash
pip install -r api/requirements-dev.txt && pip install --no-deps ./api
cd api && python -m pytest --cov=app --cov-fail-under=85   # カバレッジ閾値 85%
cd api && ruff check . && ruff format --check .
```

**フロント（Next.js）**

```bash
cd frontend && npm ci
npm test && npx tsc --noEmit && npm run build && npm run lint
```

CI（GitHub Actions `validate.yml`）は compose 検証・ruff/pytest+coverage・フロントの
型/test/build/lint・api/frontend イメージビルド・依存監査を実行します。

## 依存の固定（再現性）

- **Python (api)**: `cd api && uv pip compile pyproject.toml -o requirements.txt`（本番）/
  `uv pip compile pyproject.toml --extra dev -o requirements-dev.txt`（dev）。
- **フロント**: `cd frontend && npm install`（`package-lock.json` を更新）。
- **ComfyUI**: `comfyui/Dockerfile` の `COMFYUI_VERSION` を更新。

## コミット / PR

- ブランチ名: `<type>/issue-<番号>-<slug>`（例 `enhancement/issue-42-foo`）。
- コミット / PR タイトル: `<type>(scope): 要約`
  （type 例: `enhancement` / `fix` / `refactor` / `docs` / `reliability` / `security` / `ci` / `release` / `chore` / `test`）。
- PR 本文に `Closes #<番号>` を入れて issue と紐付ける。
- CI が緑になってからレビュー / マージする。

## Issue

バグ・機能要望は [Issue テンプレート](.github/ISSUE_TEMPLATE/) を使ってください。
セキュリティ問題は公開 issue にせず [SECURITY.md](./SECURITY.md) の手順で報告してください。

## リリース

バージョニング（SemVer）・タグ・`CHANGELOG.md`・（任意の）イメージ公開の手順は
[RELEASING.md](./RELEASING.md) を参照してください。
