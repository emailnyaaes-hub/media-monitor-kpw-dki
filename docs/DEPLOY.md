# Deploy Danita (GitHub + Vercel)

## Ringkas

| | Codespace + Cloudflare | Vercel + GitHub |
| --- | --- | --- |
| URL | Berganti setiap restart | Tetap (`*.vercel.app`) |
| Tutup Cursor | Bisa ikut mati | Tetap hidup |
| Update | Manual restart | Push ke `main` / `vercel --prod` |

Danita di Vercel memakai **Services**: frontend Vite + backend FastAPI, rewrite `/api/*` ke backend. Refresh data lewat **Cron** `GET /api/cron/ingest` setiap 2 jam (UTC).

SQLite di Vercel disimpan di `/tmp` (ephemeral): data bisa hilang saat cold start/redeploy, lalu diisi lagi oleh cron atau tombol **Perbarui sekarang**.

## Deploy dari Cursor / CLI

```bash
# sekali: login
npx vercel login

# production
npx vercel --prod --yes
```

Atau tempel `VERCEL_TOKEN` (dari [vercel.com/account/tokens](https://vercel.com/account/tokens)):

```bash
export VERCEL_TOKEN=...
npx vercel --prod --yes --token "$VERCEL_TOKEN"
```

## Connect repo di dashboard (alternatif)

1. Buka [vercel.com/new](https://vercel.com/new) → import `emailnyaaes-hub/media-monitor-kpw-dki`.
2. Root = `.` (bukan `frontend` saja) supaya `vercel.json` terbaca.
3. Deploy. URL contoh: `https://media-monitor-kpw-dki.vercel.app`.

Opsional di Project → Settings → Environment Variables:

- `CRON_SECRET` — jika diisi, cron harus mengirim `Authorization: Bearer …` (Vercel Cron default memakai User-Agent `vercel-cron`).

## Verifikasi

```bash
BASE=https://YOUR-PROJECT.vercel.app

curl -s -m 90 "$BASE/api/health"
curl -s -o /dev/null -w "login %{http_code}\n" -m 90 "$BASE/login"
curl -s -o /dev/null -w "admin %{http_code}\n" -m 90 \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  "$BASE/api/auth/login"
```

Akun: `admin` / `admin123`.

## Batasan

- Cold start pertama bisa beberapa detik.
- SQLite di `/tmp` tidak permanen antar instance; untuk data tetap jangka panjang, sambungkan Postgres (`BI_DATABASE_URL`).
- Cron timezone = UTC (`0 */2 * * *` ≈ setiap 2 jam).
