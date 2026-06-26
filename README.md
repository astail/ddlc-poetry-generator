# DDLC Poetry Generator

DDLC の4人（**Sayori / Natsuki / Yuri / Monika**）の作風で詩を **自動生成**し、
その詩から **画像** と **読み上げ音声** を作って Web で鑑賞できる、非公式ファン制作プロジェクトです。

- 📝 **詩生成**: Claude API（キャラ別 persona、英語生成＋日本語訳）
- 🎨 **画像生成**: Stable Diffusion（GTX 1060 6GB 向けに SD 1.5 アニメ調）
- 🔊 **読み上げ**: Piper（CPU・既定）/ XTTS（GPU・任意）切替対応
- 🐳 `docker compose up` で一式起動

> [!IMPORTANT]
> 本プロジェクトは **非公式・非商用のファン制作物**です。Team Salvato とは無関係で、
> 公式アセットは一切同梱しません。詳細は [DISCLAIMER.md](./DISCLAIMER.md) を必ずお読みください。

## ステータス

🚧 **設計フェーズ**。現状はリポジトリの骨組みと仕様のみ。
実装は [Issues](../../issues) のマイルストーン (M0〜M5) に沿って進めます。

## ドキュメント

- [docs/SPEC.md](./docs/SPEC.md) — 機能仕様・スコープ・キャラ作風・データモデル
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — コンテナ構成・処理フロー・GPU設計
- [DISCLAIMER.md](./DISCLAIMER.md) — 権利・ライセンス・免責

## 構成（概要）

```
frontend (Next.js) ─▶ api (FastAPI, Claude) ─▶ redis ─▶ worker-gpu (Stable Diffusion)
                              │                       └▶ worker-tts (Piper / XTTS)
                              └▶ postgres            (comfyui: GPU を占有)
```

GTX 1060 は **6GB** のため、画像生成のみ GPU を占有し、既定の読み上げは CPU(Piper) に分離します。

## 必要環境

- Docker / Docker Compose v2+
- NVIDIA GPU（GTX 1060 6GB 以上）+ ドライバ + **nvidia-container-toolkit**
- Anthropic API キー

## クイックスタート（実装完了後の想定）

```bash
cp .env.example .env       # ANTHROPIC_API_KEY 等を設定
docker compose up -d --build
# frontend: http://localhost:3000
```

> モデル（SDチェックポイント / Piper・XTTS ボイス）の取得手順は各 worker の README と
> 対応 issue を参照してください。重みはリポジトリに含めません。

## ライセンス

ソースコードは [MIT](./LICENSE)。第三者IP・モデル・APIの権利は [DISCLAIMER.md](./DISCLAIMER.md) を参照。
