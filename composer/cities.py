"""Offline ZIP code to the nearest large city in the same state."""

from __future__ import annotations

import csv
from pathlib import Path

from composer.data import find_header

NEAREST_CITY = "Nearest City"
_EXACT: dict[str, str] | None = None
_PREFIX: dict[str, str] | None = None


def nearest_city(value: str) -> str:
    code = normalize_zip(value)
    if not code:
        return ""
    exact, prefix = _tables()
    if code in exact:
        return exact[code]
    return prefix.get(code[:3], "")


def computed_fields(record: dict[str, str], headers: list[str], zip_column: str) -> dict[str, str]:
    if find_header(headers, ("nearest city",)):
        return {}
    raw = record.get(zip_column, "") if zip_column else ""
    return {NEAREST_CITY: nearest_city(raw)}


def normalize_zip(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if not digits:
        return ""
    if len(digits) >= 5:
        return digits[:5]
    return digits.zfill(5)


def _tables() -> tuple[dict[str, str], dict[str, str]]:
    global _EXACT, _PREFIX
    if _EXACT is not None and _PREFIX is not None:
        return _EXACT, _PREFIX
    exact: dict[str, str] = {}
    counts: dict[str, dict[str, int]] = {}
    with _lookup_path().open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            code = row["zip"]
            city = row["city"]
            exact[code] = city
            bucket = counts.setdefault(code[:3], {})
            bucket[city] = bucket.get(city, 0) + 1
    prefix = {key: max(cities, key=cities.get) for key, cities in counts.items()}
    _EXACT = exact
    _PREFIX = prefix
    return exact, prefix


def _lookup_path() -> Path:
    return Path(__file__).resolve().parent / "resources" / "zip_nearest_city.csv"
