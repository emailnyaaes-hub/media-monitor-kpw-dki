"""Konfigurasi bobot NLP yang bisa diubah tanpa menyentuh kode lain."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "nlp_config.json"

DEFAULT_CONFIG = {
    "weights": {
        "sentiment": 0.30,
        "reach": 0.20,
        "velocity": 0.20,
        "source": 0.15,
        "actor": 0.15,
    },
    "thresholds": {
        "positive": 0.12,
        "negative": -0.12,
        "critical_risk": 75,
        "watch_risk": 55,
    },
    "notes": (
        "Jumlah bobot sebaiknya 1,00. "
        "Sentimen mengukur nada, reach mengukur jangkauan, velocity kecepatan sebar, "
        "source kredibilitas media, actor keterlibatan tokoh."
    ),
}


def get_config() -> dict:
    if CONFIG_PATH.exists():
        with CONFIG_PATH.open(encoding="utf-8") as handle:
            stored = json.load(handle)
        merged = deepcopy(DEFAULT_CONFIG)
        merged["weights"].update(stored.get("weights", {}))
        merged["thresholds"].update(stored.get("thresholds", {}))
        if "notes" in stored:
            merged["notes"] = stored["notes"]
        return merged
    return deepcopy(DEFAULT_CONFIG)


def save_config(payload: dict) -> dict:
    weights = payload.get("weights", {})
    thresholds = payload.get("thresholds", {})
    current = get_config()
    for key in DEFAULT_CONFIG["weights"]:
        if key in weights:
            value = float(weights[key])
            if not 0 <= value <= 1:
                raise ValueError(f"Bobot {key} harus di antara 0 dan 1")
            current["weights"][key] = value
    for key in DEFAULT_CONFIG["thresholds"]:
        if key in thresholds:
            current["thresholds"][key] = float(thresholds[key])
    total = sum(current["weights"].values())
    if abs(total - 1) > 0.02:
        raise ValueError(f"Jumlah bobot saat ini {total:.2f}. Dekatkan ke 1,00")
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        json.dump(current, handle, ensure_ascii=False, indent=2)
    return current
