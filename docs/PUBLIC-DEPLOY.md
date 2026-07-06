# 外部公開ガイド（Cloudflare Tunnel）

家サーバで動かしたまま、**ルータのポート開放をせずに** TLS＋認証付きで外部公開する手順。
アプリ（api / frontend / GPU ワーカー / ComfyUI）は**すべて家サーバで動き続け**、Cloudflare は
「安全な玄関口」（TLS 終端・認証・DDoS 防御）だけを担う。`cloudflared` は Cloudflare へ
**outbound 接続**するので、インバウンドポートは一切開けない。

> ⚠️ このアプリは無認証だと `/api/generate` で Claude 課金＋GPU を消費する。**必ず Cloudflare
> Access（認証）で許可ユーザーを絞る**こと。UI 自体にログインは無い（[認証節](../README.md#認証api_auth_tokenとブラウザ-ui) 参照）。

## 1. DNS を Cloudflare に向ける（Route 53 のドメインを利用）

登録は AWS のままでよい。どちらか:

- **ドメイン全体**: Cloudflare に「Add a site」→ 提示された 2 つのネームサーバを、AWS
  （Route 53 → 登録済みドメイン → ネームサーバ編集）に設定。既存の MX 等があれば Cloudflare に再作成。
- **サブドメインだけ委任**（Route 53 を主 DNS のまま残す）: Cloudflare に `ddlc.example.com`
  をゾーン追加 → 提示 NS へ、Route 53 で `ddlc` の **NS レコードを委任**。apex や他サービスは Route 53 のまま。

いずれも **Cloudflare Free プランで無料**（追加費用は既存のドメイン更新料のみ）。

## 2. Tunnel を作成してトークンを取得

Cloudflare **Zero Trust → Networks → Tunnels → Create a tunnel**（Cloudflared 型）。

- トークンが表示されるので `.env` の `CLOUDFLARE_TUNNEL_TOKEN` に設定。
- **Public hostname** を設定（このアプリはブラウザが `/api/*` を叩くので path で振り分ける）:

  | Hostname | Path | Service |
  |---|---|---|
  | `ddlc.example.com` | `api` | `http://api:8000` |
  | `ddlc.example.com` | （空＝既定） | `http://frontend:3000` |

  ※ `cloudflared` は compose の `edge` ネットワークに居るので `api` / `frontend` を名前解決できる。

## 3. Access で認証（重要）

Zero Trust → **Access → Applications → Add**（Self-hosted、ドメイン `ddlc.example.com`）→
ポリシーで **自分のメールのみ許可**（Emails / One-time PIN 等）。**Free で 50 ユーザーまで無料**。

## 4. 公開向け `.env`

```dotenv
CLOUDFLARE_TUNNEL_TOKEN=<Cloudflare のトークン>
CORS_ALLOW_ORIGINS=https://ddlc.example.com
NEXT_PUBLIC_API_BASE=https://ddlc.example.com   # 同一ホスト /api にルーティング
POSTGRES_PASSWORD=<強いランダム値>               # change-me のまま公開は厳禁
REDIS_PASSWORD=<強いランダム値>
GENERATE_MAX_CONCURRENCY=1                        # コスト/GPU 保護
RATE_LIMIT_PER_MIN=5
# 併せて Anthropic Console で spend limit を設定しておく（最後の砦）
```

## 5. 起動

`NEXT_PUBLIC_*` はビルド時に焼き込まれるので **frontend を再ビルド**する:

```bash
docker compose --profile public up -d --build
```

- `--profile public` で `cloudflared` が起動（既定 `docker compose up` では起動しない）。
- 停止して LAN 運用へ戻すには `docker compose --profile public down` → `docker compose up -d`。

## 公開前チェックリスト

- [ ] DNS を Cloudflare に委任済み（案1 or 案2）
- [ ] Tunnel の public hostname routing（`/api`→api、既定→frontend）
- [ ] **Access ポリシーで許可ユーザーを限定**（無認証公開しない）
- [ ] 強い `POSTGRES_PASSWORD` / `REDIS_PASSWORD`
- [ ] `CORS_ALLOW_ORIGINS` / `NEXT_PUBLIC_API_BASE` を公開ドメインに設定し frontend 再ビルド
- [ ] `GENERATE_MAX_CONCURRENCY` / `RATE_LIMIT_PER_MIN` を絞る＋Anthropic spend limit
- [ ] api/frontend のポートは直接 0.0.0.0 公開しない（tunnel 経由のみ。LAN からのみ触る前提）
- [ ] db / redis / comfyui は内部ネットワークのみ（既定のまま）
- [ ] （法務）非公式・非商用のファン制作物（[DISCLAIMER.md](../DISCLAIMER.md)）。**認証付き個人利用に留め、
      誰でも使える公開サービスにはしない**（第三者 IP・Anthropic API ToS の観点）
