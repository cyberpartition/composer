"""Remember Composer preferences. Passwords are never written here."""

from __future__ import annotations

import json

from composer.paths import settings_file

DEFAULTS: dict[str, object] = {
    "geometry": "",
    "source": "",
    "sheet": "",
    "output_dir": "",
    "kind": "email",
    "subject": "",
    "body": "",
    "filename_pattern": "",
    "recipient_column": "",
    "from_name": "",
    "from_email": "",
    "smtp_host": "",
    "smtp_port": 587,
    "smtp_security": "starttls",
    "smtp_username": "",
    "body_edited": False,
    "subject_edited": False,
    "filename_edited": False,
}


def load_settings() -> dict[str, object]:
    data = dict(DEFAULTS)
    path = settings_file()
    if not path.is_file():
        return data
    try:
        stored = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return data
    if not isinstance(stored, dict):
        return data
    for key in DEFAULTS:
        if key in stored:
            data[key] = stored[key]
    return data


def save_settings(data: dict[str, object]) -> None:
    clean: dict[str, object] = {}
    for key, value in data.items():
        if "password" in key.lower():
            continue
        if key in DEFAULTS:
            clean[key] = value
    settings_file().write_text(json.dumps(clean, indent=2, ensure_ascii=False), encoding="utf-8")
