# Deploy Danita (GitHub + Vercel)

## URL produksi

**https://media-monitor-kpw-dki.vercel.app**

Akun: `admin` / `admin123`

## Cara kerja

Satu **container Docker** (`Dockerfile.vercel`) berisi frontend (Vite build) + backend (FastAPI/uvicorn). Rewrite semua traffic ke service `app`.

- Tutup Cursor **tidak** mematikan app.
- Push ke `main` + `vercel --prod`, atau hubungkan Git di dashboard Vercel untuk auto-deploy.
- Cron Hobby: `GET /api/cron/ingest` sekali sehari (`0 1 * * *` UTC ≈ 08.00 WIB). Di luar itu pakai **Perbarui sekarang**.
- SQLite di `/tmp` (ephemeral). Saat cold start, `backend/data/seed.db` disalin otomatis agar dashboard tidak kosong. Update seed: salin `monitor.db` lokal → `seed.db`, lalu redeploy. Untuk data tetap jangka panjang, set `BI_DATABASE_URL` ke Postgres.

## Deploy dari Cursor

```bash
export PATH=".tools/node/bin:$PATH"
.tools/vercel-cli/node_modules/.bin/vercel login   # sekali
.tools/vercel-cli/node_modules/.bin/vercel --prod --yes --non-interactive
```

Pastikan Root Directory proyek = `.` (bukan `frontend`), Framework = Other / Services.

## Verifikasi

```bash
BASE=https://media-monitor-kpw-dki.vercel.app
curl -s "$BASE/api/health"
curl -s -o /dev/null -w "login %{http_code}\n" "$BASE/login"
```
