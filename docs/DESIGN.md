# DESIGN — UI / デザイン

DDLC Poetry Generator フロントエンド（Next.js App Router）の UI/デザイン資料。
実装は `frontend/app/`（`globals.css` にトークンとテーマ）。

## デザイントークン

`frontend/app/globals.css` の `:root` を単一情報源とする（下表は同期。変更時は両方更新）。

### カラー

| トークン | 値 | 用途 |
|---|---|---|
| `--bg` | `#fff0f5` | 背景（ラベンダーピンク） |
| `--fg` | `#4a3540` | 本文テキスト |
| `--muted` | `#927884` | 補助テキスト |
| `--accent` | `#e35d8a` | アクセント（既定の `--char`） |
| `--card` | `#fffafc` | カード背景 |
| `--line` | `#ffd3e2` | 罫線 |
| `--line-soft` | `#f3c2d5` | 罫線（弱） |

### タイポグラフィ

| 用途 | フォント |
|---|---|
| 本文 / UI | `Zen Maru Gothic`, system-ui, sans-serif |
| 見出し / 詩 | `Klee One`, `Zen Maru Gothic`, serif |
| 一部装飾（Yuri 詩など） | `EB Garamond`, `Zen Maru Gothic`, serif |

### キャラクター別テーマ色（`data-c` / `--char`）

キャラ選択・詩カード・ギャラリーで `data-c="<id>"` により `--char` を切替える。

| キャラ | 色 |
|---|---|
| Sayori (`sayori`) | `#f0788f` |
| Natsuki (`natsuki`) | `#f06fa8` |
| Yuri (`yuri`) | `#8e6fb0` |
| Monika (`monika`) | `#4caf86` |

## 画面一覧

| 画面 | ルート / 実装 | 内容 |
|---|---|---|
| 生成 | `/` — `app/page.tsx` | キャラ選択（4）＋お題（chips 複数選択/自由入力）＋画像/音声トグル＋画像モデル選択＋追加プロンプト → 生成。結果カード（詩 EN/日本語トグル・画像・音声プレイヤー、ポーリングで後追い表示） |
| ギャラリー | `/gallery` — `app/gallery/page.tsx` | フィルタ（すべて/4キャラ）・カードグリッド・削除・ページャ |
| 詩詳細 | `/poems/[id]` — `app/poems/[id]/page.tsx` | 単一の詩の詳細表示 |
| ナビ | `app/site-nav.tsx` | Generate / Gallery ＋ 言語トグル（English / 日本語） |

## UX / 挙動メモ

- **多言語**: `LangProvider`（`app/i18n.tsx`）が UI ラベル＋生成コンテンツ言語（詩・音声）を EN/日本語で切替、cookie 永続。
- **非同期表示**: 生成直後に詩を即表示し、画像/音声は `GET /api/poems/{id}` を約 2 秒間隔でポーリングして `done`/`failed` まで追従（[docs/API.md](./API.md) の「ポーリング契約」）。
- **音声 gating**: TTS バックエンドが対応しない言語（例: Piper で日本語）は「音声を生成」を無効化（#89）。
- **アクセシビリティ**: キャラ選択は `aria-pressed`、言語トグルは `role="group"`、エラーは `role="alert"`。

## Figma / デザインファイル

> このセクションに Figma のフレーム/リンクを集約する。GitHub の Markdown は Figma 埋め込みを
> 描画しないため、**書き出した PNG を `docs/design/` に置いて参照**するか、Figma ファイルの
> リンクを貼る。`.gitignore` は `!docs/**/*.png` で画像コミットを許可済み。

- Figma ファイル: <!-- 例: https://www.figma.com/file/XXXX/DDLC-Poetry-Generator --> （未設定）
- 主要フレームの書き出し（`docs/design/*.png`）:
  - `generate.png` — 生成画面
  - `gallery.png` — ギャラリー
  - `poem-detail.png` — 詩詳細

> Figma MCP を使う場合は `/figma`（`get_screenshot` / `download_assets` / `get_variable_defs`）で
> フレーム書き出しやトークン抽出を自動化できる。デザイントークンを Figma 変数と往復させる際は
> 上のカラー/タイポ表を基準にする。
