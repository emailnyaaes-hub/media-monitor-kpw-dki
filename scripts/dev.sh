#!/usr/bin/env bash
# Menjalankan API dan tampilan sekaligus. Hentikan dengan Ctrl+C.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -x "$ROOT/.tools/node/bin/node" ]]; then
  export PATH="$ROOT/.tools/node/bin:$PATH"
fi
if ! command -v node >/dev/null 2>&1; then
  echo "Node.js 20+ belum ada. Pasang Node, atau taruh biner di .tools/node."
  exit 1
fi

cd "$ROOT/backend"
if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACK=$!

cd "$ROOT/frontend"
if [[ ! -d node_modules ]]; then
  npm install
fi
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONT=$!

trap 'kill $BACK $FRONT 2>/dev/null || true' INT TERM
wait
