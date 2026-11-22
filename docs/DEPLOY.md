# Deploy Danita

## Produksi saat ini: Cloudflare Tunnel (dari Mac/VPS)

App jalan di mesin lokal (`uvicorn` :8000), dipublikasikan lewat **Cloudflare Quick Tunnel**.

```bash
./scripts/tunnel-start.sh
# URL muncul di terminal + .tools/run/tunnel-url.txt
```

- Mac/VPS **harus tetap menyala** dan terhubung internet.
- Quick tunnel (`*.trycloudflare.com`) **URL berubah** tiap restart.
- Untuk URL tetap: buat Named Tunnel di akun Cloudflare + domain, lalu arahkan ke `http://127.0.0.1:8000`.
- Database: set `BI_DATABASE_URL` (Neon) di environment shell sebelum start, agar data tidak hanya di SQLite lokal.

Stop:

```bash
kill "$(cat .tools/run/tunnel.pid)" "$(cat .tools/run/danita.pid)"
```

## Cadangan lain

| Platform | URL | Catatan |
|---|---|---|
| Render | https://media-monitor-kpw-dki.onrender.com | Free bisa sleep; butuh `BI_DATABASE_URL` |
| Vercel | https://media-monitor-kpw-dki.vercel.app | Sering di-pause kuota Hobby |

## Ingest otomatis

- Di mode tunnel (bukan Vercel): penjadwal proses tiap 2 jam aktif di mesin yang menjalankan app.
- GitHub Actions tetap bisa memanggil `/api/cron/ingest` jika secret `APP_URL` diisi URL tunnel terkini.
