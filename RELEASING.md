# リリース手順

バージョンは [Semantic Versioning](https://semver.org/lang/ja/)（1.0 未満のため破壊的変更も MINOR で入りうる）。
タグは `vX.Y.Z`。変更履歴は [CHANGELOG.md](./CHANGELOG.md)。

## 手順

1. `CHANGELOG.md` の `[Unreleased]` を新しいバージョン見出しへ繰り下げ、日付を入れる。
2. バージョンの単一化: `api/pyproject.toml` と `frontend/package.json` の `version` を新バージョンに合わせる。
3. main にマージ後、タグを打って Release を作成する:

   ```bash
   git tag v0.1.0 && git push origin v0.1.0
   gh release create v0.1.0 --title v0.1.0 \
     --notes-file <(sed -n '/## \[0.1.0\]/,/## \[/p' CHANGELOG.md | sed '$d')
   ```

   （もしくは GitHub の **Releases → Draft a new release** から手動作成）

## コンテナイメージの公開（任意）

`.github/workflows/release.yml` は `v*.*.*` タグで api / frontend イメージを
GitHub Container Registry (ghcr) へ push できるが、**既定では無効**（誤公開防止）。

有効化するには、リポジトリの **Settings → Secrets and variables → Actions → Variables** に
リポジトリ変数 `PUBLISH_IMAGES` を `true` で追加する。公開先:

- `ghcr.io/astail/ddlc-poetry-generator-api:<version>`（および `latest`）
- `ghcr.io/astail/ddlc-poetry-generator-frontend:<version>`（および `latest`）

`comfyui` は multi-GB / GPU 前提のため push 対象外（ホスト側でビルドする）。
