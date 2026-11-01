# Jalankan gateway di mesin ini (Windows) — tanpa VPS

Gateway, dashboard, database billing, dan probe semuanya jalan di PC ini. Cloudflare hanya dipakai
sebagai pintu masuk (tunnel), jadi **tidak perlu domain baru, tidak perlu IP publik, tidak perlu
Caddy**: `cloudflared` **sudah terpasang** di `C:\Program Files (x86)\cloudflared\cloudflared`.

```
internet → Cloudflare (TLS) → cloudflared (keluar) → 127.0.0.1:8645 gateway
                                                    127.0.0.1:8680 dashboard
```

## 1. Siapkan data (sekali)

```powershell
$d = "$env:LOCALAPPDATA\merlin\gateway"
New-Item -ItemType Directory -Force -Path $d | Out-Null
```

`proxy_upstreams.json` — upstream yang benar-benar Anda punya:

```json
{
  "default": "primary",
  "upstreams": [
    {
      "name": "primary",
      "base_url": "https://api.deepseek.com/v1",
      "api_key_env": "DEEPSEEK_API_KEY",
      "models": ["deepseek-*"]
    }
  ]
}
```

`qris.txt` — payload QRIS statis Anda (satu baris, mulai `000201…`). Kalau hanya punya gambar,
decode sekali:

```powershell
& "$env:LOCALAPPDATA\merlin\merlin-agent\.venv\Scripts\python.exe" -c "import cv2,sys;from merlin_cli.proxy import qris;d,_,_=cv2.QRCodeDetector().detectAndDecode(cv2.imread(r'C:\path\qris.jpeg'));open(r'$d\qris.txt','w').write(qris.load_static(d))"
```

## 2. Jalankan

```powershell
powershell -ExecutionPolicy Bypass -File deploy\windows\start-gateway.ps1
```

Skrip ini: membuat token admin sekali (disimpan di `%LOCALAPPDATA%\merlin\gateway\admin_token.txt`),
menjalankan gateway `:8645` + dashboard `:8680` di latar belakang, menulis log ke `…\gateway\logs\`,
lalu memeriksa `/health` dan `/api/status`.

## 3. Buka ke internet (butuh klik browser Anda — tidak bisa saya lakukan)

```powershell
cloudflared tunnel login                     # pilih domain yang SUDAH ada di akun Anda
cloudflared tunnel create merlin-gateway
cloudflared tunnel route dns merlin-gateway gw.withmerlin.online     # dashboard
cloudflared tunnel route dns merlin-gateway api.withmerlin.online    # gateway
```

Isi `<TUNNEL-ID>` di `cloudflared-config.yml` (didapat dari output `tunnel create`), ganti
`__GW_HOST__` / `__API_HOST__`, lalu:

```powershell
cloudflared --config deploy\windows\cloudflared-config.yml run     # uji di depan
cloudflared --config deploy\windows\cloudflared-config.yml service install
net start cloudflared                                              # permanen
```

## 4. Verifikasi

```powershell
curl.exe -s -o NUL -w "%{http_code}`n" -X POST https://api.withmerlin.online/v1/chat/completions `
  -H "Content-Type: application/json" -d '{\"model\":\"x\",\"messages\":[]}'   # harus 401

curl.exe -N https://api.withmerlin.online/v1/chat/completions `
  -H "Authorization: Bearer mk_..." -H "Content-Type: application/json" `
  -d '{\"model\":\"deepseek-v4-flash\",\"messages\":[{\"role\":\"user\",\"content\":\"hai\"}],\"stream\":true}'
```

Streaming yang benar = potongan datang bertahap. Kalau semuanya keluar sekaligus, `chunked_transfer`
di Cloudflare sedang menahan (matikan "Rocket Loader"/buffering di zone itu).

## Batas yang harus diakui

- **Uptime = uptime PC ini.** Kalau PC sleep/mati, API mati. Untuk demo dan pelanggan awal itu
  wajar; setelah ada trafik nyata, pindahkan ke host yang menyala 24 jam (pilihan Anda, bukan
  aset orang lain).
- **Jangan** buka port 8645/8680 di firewall rumah. Tunnel tidak membutuhkannya.
- Token admin ada di file — jangan commit, jangan kirim ke chat.

## Catatan operasional (hasil uji nyata)

- Tunnel dijalankan oleh Scheduled Task `MerlinGateway` bersama gateway + dashboard, **bukan**
  Windows service. `cloudflared 2025.8.1` memasang service tanpa `--config` dan sebagai LocalSystem
  membaca config dari profil SYSTEM; hasilnya service "Running" sementara Cloudflare menjawab 530.
- Konsekuensi: layanan hidup **saat logon**, bukan saat boot. Sebelum user login, `api.withmerlin.online`
  menjawab 530/502.
- Argumen proses terbaca oleh proses lain di mesin; token admin karena itu ada di `gateway.env`
  (dibaca lewat `--env-file`), tidak pernah di command line.
- Cloudflare di zona ini menolak User-Agent `Python-urllib/*` dengan **403**. `python-requests`,
  SDK OpenAI (`OpenAI/Python x.y`), curl, dan browser lolos. Klien yang memakai urllib mentah harus
  mengirim UA sendiri.
