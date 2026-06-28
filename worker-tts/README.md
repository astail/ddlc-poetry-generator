# worker-tts

読み上げジョブのワーカー。Redis の `jobs:audio` からジョブを取り出し、詩テキストを
TTS で音声化して `/data/audio/` に保存、`audios`/`jobs` の状態を更新する。

- 実装は共有 `app` パッケージ（`app/worker_tts.py`）にあり、**api イメージを再利用**して起動します。
  compose では `worker-tts` が `build: ./api` + `command: python -m app.worker_tts`。
- 既定: **Piper**（CPU、`app/tts.py` の `PiperSynthesizer`）。ボイスモデルは初回利用時に
  `/data/voices` へダウンロード（非同梱）。`audio.lang` で `poem_en`/`poem_ja` を選択。
- キャラ別ボイス/ピッチ/速度のマッピングは #15（`app/voices.py`）。

## 言語対応（#47 / #50）

- **英語 (`lang=en`)**: Piper / XTTS いずれも対応。
- **日本語 (`lang=ja`)**: **XTTS のみ**対応（多言語モデルに `language=ja` を渡す）。
  Piper(CPU) には日本語ボイスが無いため、`lang=ja` のジョブは英語ボイスで合成して
  破綻させる代わりに、`UnsupportedLanguageError` で**即失敗**（リトライなし）し、
  `audios.error` に「`set TTS_BACKEND=xtts for Japanese`」を記録します。
  日本語の読み上げを使う場合は `TTS_BACKEND=xtts`（GPU）に切り替えてください。

## XTTS（GPU・任意, #16）

`TTS_BACKEND=xtts` で Coqui XTTS-v2 に切替（`app/tts_xtts.py`、キャラ→話者マッピング、多言語）。

有効化手順:
1. api イメージを XTTS extra 付きでビルド: `pip install ".[xtts]"`（torch を含むため重い）
2. `.env` で `TTS_BACKEND=xtts`
3. `worker-tts` に GPU を割当（compose の `deploy` ブロックをコメント解除）

> ⚠️ GTX 1060 6GB では XTTS と画像生成(SD)が VRAM を取り合います。**同時に実行しない**
> （GPU ワーカーは片方ずつ／並行度を低く）。既定は Piper(CPU) なので競合しません。
> Coqui `TTS` の import は遅延ロードで、Piper 既定イメージには torch は不要です。
