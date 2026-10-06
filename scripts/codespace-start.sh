#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="${HOME}/.local/bin:${PATH}"
python3 -m pip install --user -r backend/requirements.txt
if [ ! -f frontend/dist/index.html ]; then
  npm ci --prefix frontend
  npm run build --prefix frontend
fi
if ! curl -sf http://127.0.0.1:8000/api/health >/dev/null; then
  cd backend
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/monitor.log 2>&1 &
fi
