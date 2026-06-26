# worker-tts (Python)

読み上げジョブのワーカー。Redis から audio ジョブを取り出し、TTS で音声を生成して
`/data` に保存、`audios` を更新する。

- 既定: **Piper**（CPU・軽量・日英ボイス）。
- 任意: **XTTS**（GPU・高品質）。`TTS_BACKEND=xtts` で切替。画像生成と VRAM を
  取り合うため、XTTS 使用時はジョブを逐次化する。
- キャラ毎にボイス/ピッチ/速度をマッピング（M3 の issue）。
- ボイスモデルはリポジトリに含めない（取得手順は M3 の issue）。
