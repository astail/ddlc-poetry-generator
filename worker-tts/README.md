# worker-tts

読み上げジョブのワーカー。Redis の `jobs:audio` からジョブを取り出し、詩テキストを
TTS で音声化して `/data/audio/` に保存、`audios`/`jobs` の状態を更新する。

- 実装は共有 `app` パッケージ（`app/worker_tts.py`）にあり、**api イメージを再利用**して起動します。
  compose では `worker-tts` が `build: ./api` + `command: python -m app.worker_tts`。
- 既定: **Piper**（CPU、`app/tts.py` の `PiperSynthesizer`）。ボイスモデルは初回利用時に
  `/data/voices` へダウンロード（非同梱）。`audio.lang` で `poem_en`/`poem_ja` を選択。
- キャラ別ボイス/ピッチ/速度のマッピングは #15、XTTS(GPU) 切替は #16。
