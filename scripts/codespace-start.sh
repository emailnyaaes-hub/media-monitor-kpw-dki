#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"

publish() {
  local file="$1"
  if command -v gh >/dev/null 2>&1; then
    gh gist create --public --desc "Media Monitor KPw DKI" --filename status.txt "$file" >/tmp/gist-url.txt 2>>/tmp/monitor.log || true
  fi
}

python3 -m pip install --user -r backend/requirements.txt >>/tmp/monitor.log 2>&1 || echo "pip gagal" >>/tmp/monitor.log
if [ ! -f frontend/dist/index.html ]; then
  npm ci --prefix frontend >>/tmp/monitor.log 2>&1 || echo "npm ci gagal" >>/tmp/monitor.log
  npm run build --prefix frontend >>/tmp/monitor.log 2>&1 || echo "npm build gagal" >>/tmp/monitor.log
fi
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  (cd backend && nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >>/tmp/monitor.log 2>&1 &)
fi

for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24; do
  curl -sf http://127.0.0.1:8000/api/health >/dev/null && break
  sleep 5
done

if [ -n "${CODESPACE_NAME:-}" ] && command -v gh >/dev/null 2>&1; then
  gh codespace ports visibility 8000:public -c "$CODESPACE_NAME" >>/tmp/monitor.log 2>&1 || true
fi

if [ ! -x /tmp/cloudflared ]; then
  curl -fsSL -o /tmp/cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 || true
  chmod +x /tmp/cloudflared 2>/dev/null || true
fi
if [ -x /tmp/cloudflared ] && ! pgrep -f "cloudflared tunnel" >/dev/null 2>&1; then
  nohup /tmp/cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate >>/tmp/tunnel.log 2>&1 &
fi
public_url=""
for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15; do
  public_url="$(grep -oE 'https://[-a-z0-9]+\.trycloudflare.com' /tmp/tunnel.log 2>/dev/null | head -n 1 || true)"
  [ -n "$public_url" ] && break
  sleep 2
done

{
  echo "codespace ${CODESPACE_NAME:-tidak-diketahui}"
  echo "dashboard ${public_url:-belum-ada}"
  echo "github https://${CODESPACE_NAME:-codespace}-8000.app.github.dev"
  echo "--- health ---"
  curl -sS -m 5 http://127.0.0.1:8000/api/health || echo "health gagal"
  echo
  echo "--- log ---"
  tail -n 40 /tmp/monitor.log 2>/dev/null || true
} >/tmp/status.txt
publish /tmp/status.txt
