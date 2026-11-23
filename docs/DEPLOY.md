# Deploy Danita — Render (utama)

## URL produksi

**https://media-monitor-kpw-dki.onrender.com**

Akun default seed: `admin` / `admin123`

## Cara kerja

Satu container Docker (`Dockerfile`) = frontend Vite + backend FastAPI.

- Push ke `main` → auto-deploy Render
- Free Render: sleep ~15 menit idle; GitHub Actions tiap 2 jam bangunkan + `/api/cron/ingest`
- Database: set `BI_DATABASE_URL` (Neon) di Environment service agar data tidak hilang

## Env wajib di Render

| Key | Isi |
|---|---|
| `BI_DATABASE_URL` | URL Neon Postgres |
| `CRON_SECRET` | Sama dengan secret GitHub Actions |
| `BI_FAST_INGEST` | `1` |
| `BI_SKIP_URL_PROBE` | `1` |
| `BI_DISABLE_SCHEDULER` | `1` (ingest lewat Actions) |

## Verifikasi

```bash
BASE=https://media-monitor-kpw-dki.onrender.com
curl -sS -m 90 "$BASE/api/health"
# build harus = commit SHA terbaru di main
```

## Cadangan

| Platform | Catatan |
|---|---|
| Cloudflare Tunnel | Hanya jika Mac/VPS lokal selalu nyala (`./scripts/tunnel-start.sh`) |
| Vercel | Sering di-pause kuota Hobby |
