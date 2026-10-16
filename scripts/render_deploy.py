#!/usr/bin/env python3
"""Buat / cek layanan Danita di Render dari Cursor (butuh RENDER_API_KEY).

Ambil kunci sekali di: https://dashboard.render.com/u/settings#api-keys
Lalu:
  export RENDER_API_KEY=rnd_...
  python3 scripts/render_deploy.py
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

API = "https://api.render.com/v1"
REPO = "https://github.com/emailnyaaes-hub/media-monitor-kpw-dki"
NAME = "media-monitor-kpw-dki"


def req(method: str, path: str, body: dict | None = None) -> object:
    key = os.environ.get("RENDER_API_KEY", "").strip()
    if not key:
        raise SystemExit(
            "RENDER_API_KEY belum di-set.\n"
            "Buat di https://dashboard.render.com/u/settings#api-keys "
            "lalu: export RENDER_API_KEY=rnd_..."
        )
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "danita-deploy",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as res:
            raw = res.read().decode()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode()
        raise SystemExit(f"Render API {exc.code}: {detail}") from exc


def owners() -> list[dict]:
    rows = req("GET", "/owners")
    assert isinstance(rows, list)
    out = []
    for row in rows:
        owner = row.get("owner") if isinstance(row, dict) and "owner" in row else row
        if isinstance(owner, dict):
            out.append(owner)
    return out


def find_service(name: str) -> dict | None:
    cursor = ""
    while True:
        path = f"/services?limit=50&name={name}"
        if cursor:
            path += f"&cursor={cursor}"
        rows = req("GET", path)
        assert isinstance(rows, list)
        if not rows:
            return None
        for row in rows:
            svc = row.get("service") if isinstance(row, dict) and "service" in row else row
            if isinstance(svc, dict) and svc.get("name") == name:
                return svc
        last = rows[-1]
        cursor = last.get("cursor") if isinstance(last, dict) else None
        if not cursor:
            return None


def create_service(owner_id: str) -> dict:
    body = {
        "type": "web_service",
        "name": NAME,
        "ownerId": owner_id,
        "repo": REPO,
        "branch": "main",
        "autoDeployTrigger": "commit",
        "envVars": [
            {"key": "PYTHONUNBUFFERED", "value": "1"},
            {"key": "TZ", "value": "Asia/Jakarta"},
            {"key": "PORT", "value": "8000"},
        ],
        "serviceDetails": {
            "runtime": "docker",
            "plan": "free",
            "region": "singapore",
            "healthCheckPath": "/api/health",
            "envSpecificDetails": {
                "dockerfilePath": "./Dockerfile",
                "dockerContext": ".",
            },
        },
    }
    created = req("POST", "/services", body)
    assert isinstance(created, dict)
    return created


def wait_live(service_id: str, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        rows = req("GET", f"/services/{service_id}/deploys?limit=1")
        assert isinstance(rows, list)
        if rows:
            deploy = rows[0].get("deploy") if "deploy" in rows[0] else rows[0]
            status = deploy.get("status") if isinstance(deploy, dict) else None
            print(f"deploy status: {status}", flush=True)
            if status in {"live", "succeeded"}:
                return deploy if isinstance(deploy, dict) else {}
            if status in {"build_failed", "update_failed", "canceled", "deactivated"}:
                raise SystemExit(f"Deploy gagal: {status}")
        time.sleep(20)
    raise SystemExit("Timeout menunggu deploy")


def main() -> None:
    owns = owners()
    if not owns:
        raise SystemExit("Tidak ada workspace Render. Login dulu di dashboard.render.com dengan GitHub.")
    owner = owns[0]
    owner_id = owner.get("id")
    print(f"workspace: {owner.get('name') or owner.get('email')} ({owner_id})")

    existing = find_service(NAME)
    if existing:
        print(f"layanan sudah ada: {existing.get('serviceDetails', {}).get('url') or existing.get('dashboardUrl')}")
        svc = existing
    else:
        print("membuat layanan web Docker dari GitHub…")
        svc = create_service(str(owner_id))
        print(f"dibuat: {svc.get('id')}")

    service_id = str(svc.get("id"))
    url = (
        (svc.get("serviceDetails") or {}).get("url")
        or f"https://{NAME}.onrender.com"
    )
    print(f"URL: {url}")
    print("menunggu deploy pertama…")
    wait_live(service_id)
    print(f"siap: {url}")
    print(f"login: {url}/login  (admin / admin123)")


if __name__ == "__main__":
    main()
    sys.exit(0)
