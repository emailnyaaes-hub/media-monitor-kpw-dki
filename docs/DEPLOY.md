# Deploy Danita (GitHub + Render)

## URL produksi

**https://media-monitor-kpw-dki.onrender.com**

(Cadangan lama Vercel: `https://media-monitor-kpw-dki.vercel.app` — saat ini sering di-pause kuota.)

Akun default seed: `admin` / `admin123`

## Cara kerja

Satu **container Docker** (`Dockerfile`) berisi frontend (Vite build) + backend (FastAPI/uvicorn).

- Push ke `main` → auto-deploy Render (Blueprint / layanan yang terhubung).
- Free Render: sleep setelah ~15 menit idle; GitHub Actions tiap 2 jam membangunkan + memanggil `/api/cron/ingest`.
- Database produksi: **Neon Postgres** lewat `BI_DATABASE_URL` (salin dari proyek Neon / env Vercel lama). Tanpa ini, SQLite di disk ephemeral — data hilang saat sleep/redeploy.

## Deploy lewat Blueprint (UI)

1. Buka [dashboard.render.com](https://dashboard.render.com) → **New → Blueprint**
2. Pilih repo `emailnyaaes-hub/media-monitor-kpw-dki`
3. Isi prompt env:
   - `BI_DATABASE_URL` — URL Neon (unpooled)
   - `CRON_SECRET` — sama dengan secret di GitHub Actions
4. **Apply** / Deploy

## Deploy lewat API (dari Cursor)

```bash
export RENDER_API_KEY=rnd_...          # https://dashboard.render.com/u/settings#api-keys
export BI_DATABASE_URL='postgresql://...'
export CRON_SECRET='...'               # opsional, samakan dengan GitHub
python3 scripts/render_deploy.py
```

## Verifikasi

```bash
BASE=https://media-monitor-kpw-dki.onrender.com
# cold start bisa 30–60 detik
curl -sS -m 90 "$BASE/api/health"
curl -sS -o /dev/null -w "login %{http_code}\n" -m 90 "$BASE/login"
```
