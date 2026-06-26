# SPEC — DDLC Poetry Generator

非公式ファン制作。詳細な権利表記は [../DISCLAIMER.md](../DISCLAIMER.md) を参照。

## 1. 目的

DDLC の4キャラの作風で詩を自動生成し、その詩から「画像」と「読み上げ音声」を生成して
Web で「詩・絵・声」をまとめて鑑賞できるサービスを、単一の GTX 1060 6GB マシン上で
`docker compose` で完結させる。

## 2. スコープ

### MVP（M1〜M3）
- キャラ選択（Sayori / Natsuki / Yuri / Monika / ランダム / 全員）＋お題（任意）入力
- Claude による詩生成（**英語生成 + 日本語訳**を同時取得）
- 詩→画像（Stable Diffusion 1.5 アニメ調）
- 詩の読み上げ（Piper, CPU。日英ボイス）
- 生成物の保存・一覧（ギャラリー/履歴）

### Phase 2（M5）
- XTTS（GPU, 声の表現力向上）への切替（既に切替設計は導入）
- SDXL 対応（6GB は offload 前提で低速）
- 認証 / レート制限の強化 / 多言語拡充

### 非スコープ
- 公式アセット（立ち絵・音楽・フォント・音声）の利用や同梱
- 商用利用
- 原作ストーリーの再現・改変配布

## 3. キャラクター作風（詩生成 persona）

| キャラ | 作風の要点 | 画像の方向性（例） |
|---|---|---|
| **Sayori** | 平易・口語的、明るさの裏に憂い。素直で短め。 | 暖色、柔らかい光、空・朝、ほんのり寂しさ |
| **Natsuki** | 短く可愛く、勢いとツン。リズミカル。 | ポップ、パステル、お菓子・かわいい小物 |
| **Yuri** | 難語・耽美・暗く重厚、長め。比喩多用。 | 暗色、紫、ナイフ/紅茶/書物、陰影強い |
| **Monika** | メタ的・哲学的・自己言及。整然。 | 緑、整った構図、現実と虚構の境界、静謐 |

各キャラは system prompt（persona＋作風ガイド＋禁止事項）で表現する。原作テキストの
丸写しは行わず、作風を踏まえた**新規創作**を生成する。

## 4. 主要ユースケース

1. ユーザがキャラ＋お題を選ぶ → 「生成」
2. 詩が数秒で表示される（英＋日）
3. 画像が後追いで表示される（5〜15秒）
4. 「再生」で読み上げ音声が流れる
5. 生成物はギャラリー/履歴から再閲覧できる

## 5. Claude 連携設計

詩・画像プロンプト・読み上げヒントを **1コールの構造化出力**でまとめて取得し、
トークン効率と一貫性を確保する。

出力スキーマ（例）:
```json
{
  "title": "詩のタイトル",
  "character": "yuri",
  "poem_en": "English poem text...",
  "poem_ja": "日本語訳...",
  "image_prompt": "danbooru-style tags / scene description for SD",
  "image_negative": "lowres, bad anatomy, ...",
  "mood": "melancholic",
  "voice_hints": { "rate": 0.95, "pitch": -1 }
}
```

- モデルは `POEM_MODEL`（既定: Claude Sonnet）で差し替え可能。
- temperature は高め（創作向け、既定 1.0）。
- リトライ/タイムアウト/トークン上限を実装。同一(キャラ,お題)のキャッシュは任意。

## 6. データモデル（概略）

- **poems**: id, character, theme, lang, title, poem_en, poem_ja, mood, model, created_at
- **images**: id, poem_id, prompt, negative, checkpoint, seed, width, height, path, status
- **audios**: id, poem_id, backend(piper/xtts), voice, lang, path, status
- **jobs**: id, type(image/audio), ref_id, status(queued/running/done/failed), error, timestamps

## 7. API（概略）

- `POST /api/generate` — キャラ・お題を受け、詩を生成して返す＋画像/音声ジョブを投入
- `GET  /api/poems` / `GET /api/poems/{id}` — 一覧/詳細
- `GET  /api/poems/{id}/status` (SSE) — 画像・音声の生成進捗
- `GET  /api/assets/{...}` — 生成画像・音声の配信

## 8. 制約・前提

- GPU は GTX 1060 **6GB** 1枚。画像生成(SD)のみ GPU を占有し、既定の読み上げは
  CPU(Piper) に分離して VRAM 競合を避ける。XTTS(GPU) は逐次化前提のオプション。
- 重み・生成物はリポジトリに含めない（`.gitignore` 済）。`/data` ボリュームに保存。

## 9. マイルストーン

| MS | 内容 |
|---|---|
| M0 | リポジトリ基盤 / compose skeleton / CI(lint) / データモデル定義 |
| M1 | 詩生成（Claude＋persona＋API＋最小表示UI＋永続化） |
| M2 | 画像生成（ComfyUI＋GPU＋ワークフロー＋非同期表示） |
| M3 | 読み上げ（Piper＋キャラ別ボイス＋XTTS切替＋プレイヤー） |
| M4 | 仕上げ（DDLC風UI / ギャラリー / エラー処理 / レート制限 / ドキュメント） |
| M5 | Phase2（SDXL / XTTS本格化 / 多言語 / 認証） |
