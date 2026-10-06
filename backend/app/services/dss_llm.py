"""Penyedia model bahasa yang bisa diganti.

Tanpa LLM_API_KEY, modul saran memakai teks yang disalin dari database.
Jika kunci ada, model hanya boleh mengubah bagian inferensi. Fakta dan tautan
tetap dari item yang sudah diambil. Keluaran yang memuat tautan asing ditolak.
"""

from __future__ import annotations

import json
import os
import urllib.request

PROMPT_VERSION = "dss-1"
GROUNDED_MODEL = "penyusun-terkunci-data"

SYSTEM_PROMPT = """Anda membantu tim kehumasan Bank Indonesia menyusun saran internal.
Anda bukan pengambil keputusan. Tulis dalam Bahasa Indonesia yang formal dan netral.

Aturan:
- Jangan mengarang fakta, angka, kutipan, nama media, atau tautan.
- Setiap klaim harus bisa ditelusuri ke bukti yang diberikan. Jangan menambah sumber.
- Jangan menulis URL yang tidak ada di daftar bukti.
- Bedakan fakta (sudah diberikan) dan inferensi. Jangan menyamar inferensi sebagai fakta.
- Jangan menyarankan publikasi otomatis. Saran ini hanya untuk ditinjau manusia.
- Ini masukan persepsi publik, bukan rekomendasi kebijakan moneter.
- Jika bukti kurang, jangan memaksakan rekomendasi.
Balas hanya JSON dengan kunci: recommendation, draft_points, alternatives, reason, impact_follow, impact_ignore, inferences.
alternatives adalah array objek {option, tradeoff}, minimal satu.
"""


def configured_model() -> str:
    if os.environ.get("LLM_API_KEY", "").strip():
        return os.environ.get("LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    return GROUNDED_MODEL


def rewrite_inference(card: dict) -> dict | None:
    """Kembalikan bagian inferensi bila lolos validasi. None bila tidak dipakai."""
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key or card.get("insufficient"):
        return None
    evidence = card.get("evidence") or []
    allowed = {item.get("url") for item in evidence if item.get("url")}
    if not allowed:
        return None
    user = json.dumps(
        {
            "judul": card.get("title"),
            "fakta": card.get("facts"),
            "bukti": [
                {"id": item.get("mention_id"), "judul": item.get("title"), "sumber": item.get("source_name"), "url": item.get("url")}
                for item in evidence
            ],
            "nada": card.get("tone") or "formal netral",
        },
        ensure_ascii=False,
    )
    raw = _complete(SYSTEM_PROMPT, user, key)
    if not raw:
        return None
    parsed = _parse_json(raw)
    if not parsed or not _valid(parsed, allowed, card.get("facts") or []):
        return None
    return parsed


def answer_question(question: str, facts: list[str], evidence: list[dict]) -> str | None:
    key = os.environ.get("LLM_API_KEY", "").strip()
    if not key or len(evidence) < 1:
        return None
    allowed = {item["url"] for item in evidence}
    user = json.dumps({"pertanyaan": question, "fakta": facts, "bukti": evidence}, ensure_ascii=False)
    system = SYSTEM_PROMPT + " Jawab pertanyaan analis hanya dari fakta yang diberikan. Jangan menambah sumber."
    raw = _complete(system, user, key)
    if not raw:
        return None
    if _unknown_url(raw, allowed):
        return None
    return raw.strip()[:2000]


def _complete(system: str, user: str, key: str) -> str | None:
    base = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1").rstrip("/")
    model = configured_model()
    body = json.dumps(
        {
            "model": model,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
    ).encode()
    request = urllib.request.Request(
        base + "/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8", "replace"))
        return payload["choices"][0]["message"]["content"]
    except Exception:
        return None


def _parse_json(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _valid(data: dict, allowed_urls: set[str], facts: list[str]) -> bool:
    recommendation = str(data.get("recommendation") or "").strip()
    alternatives = data.get("alternatives")
    if not recommendation or not isinstance(alternatives, list) or not alternatives:
        return False
    blob = json.dumps(data, ensure_ascii=False)
    if _unknown_url(blob, allowed_urls):
        return False
    fact_blob = " ".join(facts)
    for token in _long_numbers(blob):
        if token not in fact_blob and token not in " ".join(allowed_urls):
            return False
    return True


def _unknown_url(text: str, allowed: set[str]) -> bool:
    import re

    for found in re.findall(r"https?://[^\s\"']+", text):
        clean = found.rstrip(").,;")
        if clean not in allowed:
            return True
    return False


def _long_numbers(text: str) -> list[str]:
    import re

    return re.findall(r"\d{4,}", text)
