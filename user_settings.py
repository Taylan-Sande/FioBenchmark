"""Persistência simples de preferências do usuário."""

from __future__ import annotations

import json
from pathlib import Path

SETTINGS_DIR = Path.home() / "FioBenchmark"
SETTINGS_FILE = SETTINGS_DIR / "config.json"

DEFAULTS = {
    "target_root": "",
    "results_root": str(SETTINGS_DIR / "resultados"),
    "dark_mode": False,
    "last_session": "",
}


def load_settings() -> dict:
    data = dict(DEFAULTS)
    try:
        if SETTINGS_FILE.is_file():
            raw = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({k: raw[k] for k in DEFAULTS if k in raw})
    except (OSError, json.JSONDecodeError, TypeError):
        pass
    return data


def save_settings(updates: dict) -> None:
    data = load_settings()
    data.update(updates)
    try:
        SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
