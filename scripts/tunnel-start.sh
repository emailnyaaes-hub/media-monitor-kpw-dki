#!/usr/bin/env bash
# Jalankan DANITA lokal + Cloudflare Quick Tunnel (trycloudflare.com).
# Mac/VPS harus tetap menyala. URL berubah tiap restart kecuali pakai named tunnel.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CF="${ROOT}/.tools/cloudflared"
LOG_DIR="${ROOT}/.tools/run"
mkdir -p "$LOG_DIR"
APP_LOG="${LOG_DIR}/danita.log"
TUN_LOG="${LOG_DIR}/tunnel.log"
URL_FILE="${LOG_DIR}/tunnel-url.txt"
PID_APP="${LOG_DIR}/danita.pid"
PID_TUN="${LOG_DIR}/tunnel.pid"

if [[ -x "${ROOT}/.tools/node/bin/node" ]]; then
  export PATH="${ROOT}/.tools/node/bin:$PATH"
fi

if [[ ! -x "$CF" ]]; then
  echo "cloudflared belum ada di .tools/cloudflared"
  exit 1
fi

# Hentikan proses lama dari skrip ini.
if [[ -f "$PID_TUN" ]] && kill -0 "$(cat "$PID_TUN")" 2>/dev/null; then
  kill "$(cat "$PID_TUN")" 2>/dev/null || true
fi
if [[ -f "$PID_APP" ]] && kill -0 "$(cat "$PID_APP")" 2>/dev/null; then
  kill "$(cat "$PID_APP")" 2>/dev/null || true
fi
# Jangan bunuh uvicorn orang lain sembarangan; hanya port 8000 milik kita jika sehat.
sleep 1

cd "$ROOT/backend"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -U pip
  .venv/bin/pip install -r requirements.txt
fi

# Frontend dist (SPA dilayani FastAPI).
if [[ ! -f "$ROOT/frontend/dist/index.html" ]]; then
  if command -v npm >/dev/null 2>&1; then
    npm ci --prefix "$ROOT/frontend"
    npm run build --prefix "$ROOT/frontend"
  else
    echo "frontend/dist belum ada dan npm tidak tersedia"
    exit 1
  fi
fi

export BI_FAST_INGEST="${BI_FAST_INGEST:-1}"
export BI_SKIP_URL_PROBE="${BI_SKIP_URL_PROBE:-1}"
# Biarkan penjadwal lokal jalan (bukan Vercel).
unset VERCEL VERCEL_ENV VERCEL_URL 2>/dev/null || true
export BI_DISABLE_SCHEDULER="${BI_DISABLE_SCHEDULER:-0}"

if curl -sf -m 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
  echo "API sudah jalan di :8000"
else
  : >"$APP_LOG"
  # Detach dari session shell Cursor agar proses tidak ikut mati.
  (
    cd "$ROOT/backend"
    exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
  ) >>"$APP_LOG" 2>&1 &
  disown $! 2>/dev/null || true
  echo $! >"$PID_APP"
  for _ in $(seq 1 30); do
    curl -sf -m 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1 && break
    sleep 1
  done
  if ! curl -sf -m 2 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
    echo "Gagal start API. Lihat $APP_LOG"
    tail -n 40 "$APP_LOG" || true
    exit 1
  fi
  echo "API OK (pid $(cat "$PID_APP"))"
fi

: >"$TUN_LOG"
(
  exec "$CF" tunnel --url http://127.0.0.1:8000 --no-autoupdate
) >"$TUN_LOG" 2>&1 &
disown $! 2>/dev/null || true
echo $! >"$PID_TUN"

URL=""
for _ in $(seq 1 40); do
  URL="$(grep -oE 'https://[-a-z0-9]+\.trycloudflare\.com' "$TUN_LOG" 2>/dev/null | head -n 1 || true)"
  [[ -n "$URL" ]] && break
  sleep 1
done

if [[ -z "$URL" ]]; then
  echo "Tunnel gagal. Lihat $TUN_LOG"
  tail -n 30 "$TUN_LOG" || true
  exit 1
fi

printf '%s\n' "$URL" >"$URL_FILE"
echo "DANITA tunnel: $URL"
echo "URL disimpan di $URL_FILE"
echo "Stop: kill \$(cat $PID_TUN) \$(cat $PID_APP)"
