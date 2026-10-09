#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"
REPO="emailnyaaes-hub/media-monitor-kpw-dki"

note() {
  printf '%s\n' "$1" >>/tmp/status.txt
  [ -n "${GITHUB_TOKEN:-}" ] || return 0
  python3 - "$REPO" <<'PY'
import base64, json, os, sys, urllib.request
repo, token = sys.argv[1], os.environ.get("GITHUB_TOKEN", "")
text = open("/tmp/status.txt", "rb").read()
url = f"https://api.github.com/repos/{repo}/contents/DEPLOY_STATUS.txt"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github+json",
    "User-Agent": "monitor",
    "Content-Type": "application/json",
}
sha = None
try:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as res:
        sha = json.load(res).get("sha")
except Exception:
    pass
body = {"message": "Status deploy", "content": base64.b64encode(text).decode()}
if sha:
    body["sha"] = sha
put = urllib.request.Request(url, data=json.dumps(body).encode(), headers=headers, method="PUT")
try:
    urllib.request.urlopen(put, timeout=20).read()
except Exception as exc:
    open("/tmp/note-err.txt", "a").write(str(exc) + "\n")
PY
}

: >/tmp/status.txt
note "mulai $(date -u +%H:%M:%S)"
PY=/tmp/venv/bin/python
if [ ! -x "$PY" ]; then
  BASE=""
  for candidate in python3.12 python3.11 python3.10; do
    if command -v "$candidate" >/dev/null 2>&1; then
      BASE="$candidate"
      break
    fi
  done
  if [ -z "$BASE" ]; then
    sudo apt-get update >>/tmp/monitor.log 2>&1 || true
    sudo apt-get install -y python3.11 python3.11-venv >>/tmp/monitor.log 2>&1 || note "python3.11 gagal dipasang"
    BASE=python3.11
  fi
  note "python $($BASE --version 2>&1)"
  if ! "$BASE" -m venv /tmp/venv >>/tmp/monitor.log 2>&1; then
    sudo apt-get update >>/tmp/monitor.log 2>&1 || true
    sudo apt-get install -y python3-venv "${BASE}-venv" >>/tmp/monitor.log 2>&1 || note "venv paket gagal"
    rm -rf /tmp/venv
    "$BASE" -m venv /tmp/venv >>/tmp/monitor.log 2>&1 || note "venv gagal: $(tail -n 6 /tmp/monitor.log)"
  fi
fi
if [ -x "$PY" ]; then
  "$PY" -m pip install -U pip >>/tmp/monitor.log 2>&1 || true
fi
if [ -x "$PY" ]; then
  "$PY" -m pip install -r backend/requirements.txt >>/tmp/monitor.log 2>&1 || note "pip gagal: $(tail -n 8 /tmp/monitor.log)"
else
  note "pip gagal: python venv tidak ada"
fi
note "pip selesai"
if [ ! -f frontend/dist/index.html ]; then
  npm ci --prefix frontend >>/tmp/monitor.log 2>&1 || note "npm ci gagal"
  npm run build --prefix frontend >>/tmp/monitor.log 2>&1 || note "npm build gagal"
fi
note "frontend selesai"
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  (cd backend && nohup "$PY" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >>/tmp/monitor.log 2>&1 &)
fi
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null && break
  sleep 5
done
if curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  note "health ok"
else
  note "health gagal"
  note "$(tail -n 20 /tmp/monitor.log 2>/dev/null || true)"
fi
if [ ! -x /tmp/cloudflared ]; then
  curl -fsSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 >>/tmp/monitor.log 2>&1 || note "unduh tunnel gagal"
  chmod +x /tmp/cloudflared 2>/dev/null || true
fi
if [ -x /tmp/cloudflared ]; then
  nohup /tmp/cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate > /tmp/tunnel.log 2>&1 &
fi
direct=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
  direct="$(grep -oE 'https://[-a-z0-9]+\.trycloudflare.com' /tmp/tunnel.log 2>/dev/null | head -n 1 || true)"
  [ -n "$direct" ] && break
  sleep 2
done
if [ -n "$direct" ]; then
  note "langsung $direct"
else
  note "langsung gagal"
  note "$(tail -n 12 /tmp/tunnel.log 2>/dev/null || true)"
fi
note "selesai $(date -u +%H:%M:%S)"
