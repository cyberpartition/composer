"""Locations Composer uses for its logo, sample file, and settings."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent.parent


ROOT = bundle_root()


def logo_dark_svg() -> Path:
    return ROOT / "logo" / "composer-logo-dark.svg"


def logo_dark_png() -> Path:
    return ROOT / "logo" / "composer-logo-dark.png"


def mark_svg() -> Path:
    return ROOT / "logo" / "composer-mark.svg"


def mark_png() -> Path:
    return ROOT / "logo" / "composer-mark.png"


def sample_csv() -> Path:
    return ROOT / "samples" / "contacts.csv"


def settings_dir() -> Path:
    override = os.environ.get("COMPOSER_SETTINGS_DIR")
    if override:
        folder = Path(override)
    else:
        base = os.environ.get("APPDATA") or str(Path.home())
        folder = Path(base) / "Composer"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def settings_file() -> Path:
    return settings_dir() / "settings.json"


def default_output_dir() -> Path:
    documents = Path.home() / "Documents"
    base = documents if documents.is_dir() else Path.home()
    return base / "Composer"
