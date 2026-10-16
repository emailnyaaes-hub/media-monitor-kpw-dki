# Deploy Danita (GitHub + Render)

## Ringkas

| | Codespace + Cloudflare | Render + GitHub |
| --- | --- | --- |
| URL | Berganti setiap restart | Tetap (`*.onrender.com`) |
| Tutup Cursor | Bisa ikut mati (idle) | Tetap hidup |
| Update | Manual restart | Push ke `main` |

## Apply Blueprint (satu kali)

1. Login [Render](https://dashboard.render.com) dengan GitHub.
2. **New** → **Blueprint** → repo `media-monitor-kpw-dki`, branch `main`.
3. Pastikan file `render.yaml` terbaca, lalu **Apply**.
4. Di layanan web, salin **Public URL**.

## Verifikasi setelah live

Ganti `BASE` dengan URL Render Anda.

```bash
BASE=https://media-monitor-kpw-dki.onrender.com

# Bisa lambat 30–60 detik jika free plan baru bangun dari sleep
curl -s -m 90 "$BASE/api/health"
curl -s -o /dev/null -w "login %{http_code}\n" -m 90 "$BASE/login"
curl -s -o /dev/null -w "admin %{http_code}\n" -m 90 \
  -X POST -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' \
  "$BASE/api/auth/login"
```

Yang diharapkan:

- `/api/health` → `"status":"ok"`
- `/login` → `200`
- login admin → `200`
- Logo BI: `$BASE/img/bi-logo-white.png` → `200`
- Setelah fetch pertama (beberapa menit), `mentions` di health naik; grafik Ringkasan terisi

## Redeploy

```bash
git push origin main
```

Render membangun ulang image Docker. Pantau log di dashboard Render.

## Batasan free plan

- Sleep setelah idle ~15 menit; cold start lambat.
- SQLite tanpa persistent disk: data hilang saat redeploy, lalu diisi ulang oleh scheduler.
- Untuk nyala 24 jam tanpa sleep dan disk tetap, naikkan ke paket berbayar di Render (atau VPS).
