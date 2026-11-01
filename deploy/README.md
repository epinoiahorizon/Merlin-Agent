# Deploy Merlin Gateway

Dua layanan + satu reverse proxy. Gateway (OpenAI-compatible, metered) dan dashboard (status +
top-up QRIS) jalan sebagai container; TLS/domain ditangani proxy di host.

```
Cloudflare (proxied) → nginx/Caddy di host → 127.0.0.1:8645 (gateway) | 127.0.0.1:8680 (dashboard)
```

## Dua jalur TLS

| | nginx (disarankan) | Caddy |
|---|---|---|
| Syarat | nginx + certbot sudah ada di host | paket Caddy + Origin CA cert dari Cloudflare |
| Port | 80/443 (dipakai bersama domain lain) | **8443** (80/443 sudah dipegang nginx) |
| Sertifikat | Let's Encrypt via certbot (auto-renew) | Cloudflare Origin CA, tanpa ACME |
| File | `nginx-gateway.conf` | `Caddyfile` |

Alasan nginx jadi default: host target sudah menjalankan nginx + certbot untuk beberapa domain,
jadi menambah `server` block tidak menambah proses baru maupun jalur sertifikat baru. Caddy tetap
tersedia (`deploy/Caddyfile`) kalau ingin konfigurasi yang lebih ringkas — tapi harus di port 8443.

## 1. Siapkan direktori dan konfigurasi

```bash
sudo mkdir -p /srv/merlin/{data,config}
sudo cp deploy/docker-compose.gateway.yml /srv/merlin/docker-compose.yml
sudo cp deploy/Dockerfile.gateway         /srv/merlin/deploy/Dockerfile.gateway

# upstream (NAMA file harus proxy_upstreams.json — lihat adapters/generic.py)
sudo tee /srv/merlin/config/proxy_upstreams.json >/dev/null <<'JSON'
{
  "default": "primary",
  "upstreams": [
    { "name": "primary", "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "PRIMARY_KEY", "models": ["deepseek-*"] }
  ]
}
JSON

# payload QRIS statis (boleh file .txt berisi string, atau .jpg/.png hasil scan)
sudo cp qris.txt /srv/merlin/config/qris.txt
```

Rahasia disimpan di `.env` (jangan di compose):

```bash
sudo tee /srv/merlin/.env >/dev/null <<'ENV'
MERLIN_PROXY_ADMIN_TOKEN=<openssl rand -base64 24>
MERLIN_PROXY_WEBHOOK_SECRET=<openssl rand -hex 32>
MERLIN_PROXY_INVOICE_TTL=1800
ENV
sudo chmod 600 /srv/merlin/.env
```

> `api_key_env` dibaca dari environment **container**. Tambahkan ke `environment:` pada compose atau
> pakai `api_key` langsung bila Anda menerima risiko menyimpan rahasia di file.

## 2. Seed tenant pertama

Gateway menolak semua request tanpa key tenant (`401 invalid_api_key`). Buat satu:

```bash
cd /path/ke/merlin-agent
MERLIN_PROXY_LEDGER=/srv/merlin/data/ledger.db \
  python -c "
from merlin_cli.proxy.tenants import LedgerStore
s = LedgerStore()
t = s.create_tenant('acme', initial_micros=25_000_000_000)   # Rp 25.000
print(s.issue_key(t, 'first-key'))"
```

Satuan: **micros**. Kalau menagih rupiah, 1 IDR = 1 000 000 micros.

## 3. Jalankan

```bash
cd /srv/merlin && sudo docker compose up -d --build
sudo docker compose ps
curl -s http://127.0.0.1:8645/health        # {"status":"ok",...}
curl -s http://127.0.0.1:8680/api/status | head -c 200
```

## 4. Pasang reverse proxy

nginx (dua subdomain, satu cert):

```bash
sudo cp deploy/nginx-gateway.conf /etc/nginx/sites-available/merlin-gateway
sudo sed -i "s/__GW_DOMAIN__/gw.domain.com/g; s/__API_DOMAIN__/api.domain.com/g" \
     /etc/nginx/sites-available/merlin-gateway
sudo ln -sf /etc/nginx/sites-available/merlin-gateway /etc/nginx/sites-enabled/merlin-gateway
sudo certbot --nginx -d gw.domain.com -d api.domain.com
sudo nginx -t && sudo systemctl reload nginx
```

Di Cloudflare: **A record proxied** (oranye) untuk kedua nama → IP host, SSL mode **Full (strict)**.
Jangan aktifkan "Rocket Loader" atau "Cache Everything" di `api.` — streaming SSE bisa rusak.

Caddy (alternatif, port 8443): buat Origin CA cert di Cloudflare, simpan di `/etc/caddy/origin.pem`
+ `origin.key`, isi domain di `deploy/Caddyfile`, lalu `caddy run --config /etc/caddy/Caddyfile`.
Di Cloudflare arahkan origin ke `https://host:8443` (Origin Rules → port 8443 didukung CF).

## 5. Verifikasi sungguhan

```bash
# 401 tanpa key
curl -s -o /dev/null -w "%{http_code}\n" -X POST https://api.domain.com/v1/chat/completions \
  -H 'Content-Type: application/json' -d '{"model":"x","messages":[]}'

# 200 + streaming dengan key tenant
curl -N https://api.domain.com/v1/chat/completions \
  -H "Authorization: Bearer mk_..." -H 'Content-Type: application/json' \
  -d '{"model":"deepseek-v4-flash","messages":[{"role":"user","content":"hai"}],"stream":true}'
```

Streaming yang benar: potongan muncul bertahap, bukan sekaligus di akhir. Kalau sekaligus,
`proxy_buffering off` (nginx) atau `flush_interval -1` (Caddy) belum aktif.

## 6. Cron

```cron
*/15 * * * * cd /srv/merlin && MERLIN_PROXY_LEDGER=/srv/merlin/data/ledger.db \
  MERLIN_PROXY_PROBES=/srv/merlin/data/ledger.db docker compose exec -T gateway \
  python -m merlin_cli.proxy.entry serve --help >/dev/null 2>&1 || true
```

Perintah maintenance lengkap (`catalog sync`, `probe run`, expire invoice) ada di CLI penuh
(`merlin proxy maintenance`); di container cukup jalankan dari host dengan `MERLIN_PROXY_LEDGER`
menunjuk file DB yang sama.

## Catatan operasional

- **SQLite dipakai bersama** oleh dua container di satu host (mode WAL) — aman di filesystem lokal,
  jangan di NFS.
- **Disk**: image Python + dua dep ≈ 200 MB. Host target punya ~12 GB bebas; jangan menambah
  database besar tanpa memantau `df`.
- **Backup**: `sqlite3 /srv/merlin/data/ledger.db ".backup /srv/merlin/data/backup-$(date +%F).db"`
  seminggu sekali — file ini berisi saldo, tagihan, dan riwayat harga.
- **Jangan** expose `8645`/`8680` ke 0.0.0.0 di firewall host; bind 127.0.0.1 sudah dilakukan compose.
