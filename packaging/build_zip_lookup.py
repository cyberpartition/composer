"""Build the offline ZIP to nearest-large-city table from Census files.

Download the inputs first into a folder (see the constants below), then run:

    python packaging/build_zip_lookup.py C:\\path\\to\\composer-geo
"""

from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "composer" / "resources" / "zip_nearest_city.csv"
LARGE_POPULATION = 50_000
MEDIUM_POPULATION = 10_000

STATE_ABBR = {
    "Alabama": "AL",
    "Alaska": "AK",
    "Arizona": "AZ",
    "Arkansas": "AR",
    "California": "CA",
    "Colorado": "CO",
    "Connecticut": "CT",
    "Delaware": "DE",
    "District of Columbia": "DC",
    "Florida": "FL",
    "Georgia": "GA",
    "Hawaii": "HI",
    "Idaho": "ID",
    "Illinois": "IL",
    "Indiana": "IN",
    "Iowa": "IA",
    "Kansas": "KS",
    "Kentucky": "KY",
    "Louisiana": "LA",
    "Maine": "ME",
    "Maryland": "MD",
    "Massachusetts": "MA",
    "Michigan": "MI",
    "Minnesota": "MN",
    "Mississippi": "MS",
    "Missouri": "MO",
    "Montana": "MT",
    "Nebraska": "NE",
    "Nevada": "NV",
    "New Hampshire": "NH",
    "New Jersey": "NJ",
    "New Mexico": "NM",
    "New York": "NY",
    "North Carolina": "NC",
    "North Dakota": "ND",
    "Ohio": "OH",
    "Oklahoma": "OK",
    "Oregon": "OR",
    "Pennsylvania": "PA",
    "Rhode Island": "RI",
    "South Carolina": "SC",
    "South Dakota": "SD",
    "Tennessee": "TN",
    "Texas": "TX",
    "Utah": "UT",
    "Vermont": "VT",
    "Virginia": "VA",
    "Washington": "WA",
    "West Virginia": "WV",
    "Wisconsin": "WI",
    "Wyoming": "WY",
    "Puerto Rico": "PR",
}

NAME_SUFFIXES = (
    " metropolitan government",
    " metro government",
    " unified government",
    " consolidated government",
    " urban county",
    " municipality",
    " borough",
    " village",
    " city",
    " town",
    " cdp",
)


# The 56 FBI field offices. Coordinates are the office locations.
# Nashville replaced the Knoxville and Memphis field offices.
# Billings is the Montana field office. Norfolk remains a field office.
FBI_FIELD_OFFICES = (
    ("Albany", "NY", 42.635131, -73.773212),
    ("Albuquerque", "NM", 35.12884, -106.613572),
    ("Anchorage", "AK", 61.21664, -149.88223),
    ("Atlanta", "GA", 33.846091, -84.307531),
    ("Baltimore", "MD", 39.32828, -76.746672),
    ("Billings", "MT", 45.7833, -108.5059),
    ("Birmingham", "AL", 33.523481, -86.815631),
    ("Boston", "MA", 42.39754, -71.038499),
    ("Buffalo", "NY", 42.887711, -78.879491),
    ("Charlotte", "NC", 35.140511, -80.920471),
    ("Chicago", "IL", 41.866591, -87.680001),
    ("Cincinnati", "OH", 39.208789, -84.396799),
    ("Cleveland", "OH", 41.50828, -81.686052),
    ("Columbia", "SC", 34.061201, -81.129961),
    ("Dallas", "TX", 32.853981, -96.887752),
    ("Denver", "CO", 39.76725, -104.895602),
    ("Detroit", "MI", 42.331621, -83.053842),
    ("El Paso", "TX", 31.816181, -106.536761),
    ("Honolulu", "HI", 21.321131, -158.06613),
    ("Houston", "TX", 29.834411, -95.481732),
    ("Indianapolis", "IN", 39.91061, -86.059172),
    ("Jackson", "MS", 32.39486, -90.190341),
    ("Jacksonville", "FL", 30.247521, -81.521872),
    ("Kansas City", "MO", 39.09699, -94.593252),
    ("Las Vegas", "NV", 36.195671, -115.164121),
    ("Little Rock", "AR", 34.741511, -92.395232),
    ("Los Angeles", "CA", 33.810929, -118.136751),
    ("Louisville", "KY", 38.217691, -85.528741),
    ("Miami", "FL", 25.990296, -80.33516),
    ("Milwaukee", "WI", 42.978595, -87.858621),
    ("Minneapolis", "MN", 45.072819, -93.301082),
    ("Mobile", "AL", 30.692301, -88.040871),
    ("Nashville", "TN", 36.1437, -86.6798),
    ("New Haven", "CT", 41.308721, -72.920052),
    ("New Orleans", "LA", 30.030081, -90.041901),
    ("New York", "NY", 40.712628, -74.009709),
    ("Newark", "NJ", 40.73866, -74.164371),
    ("Norfolk", "VA", 36.856934, -76.211773),
    ("Oklahoma City", "OK", 35.615442, -97.574299),
    ("Omaha", "NE", 41.214641, -96.102512),
    ("Philadelphia", "PA", 39.95271, -75.149992),
    ("Phoenix", "AZ", 33.683761, -112.065581),
    ("Pittsburgh", "PA", 40.42159, -79.958742),
    ("Portland", "OR", 45.575805, -122.565449),
    ("Richmond", "VA", 37.63899, -77.483131),
    ("Sacramento", "CA", 38.793838, -121.305308),
    ("Salt Lake City", "UT", 40.775567, -112.021082),
    ("San Antonio", "TX", 29.57088, -98.597612),
    ("San Diego", "CA", 32.89622, -117.215298),
    ("San Francisco", "CA", 37.779847, -122.418985),
    ("San Juan", "PR", 18.42333, -66.069272),
    ("Seattle", "WA", 47.60665, -122.33488),
    ("Springfield", "IL", 39.764491, -89.643441),
    ("St. Louis", "MO", 38.630521, -90.212751),
    ("Tampa", "FL", 27.94819, -82.537291),
    ("Washington", "DC", 38.897634, -77.015957),
)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Pass the folder that contains the Census downloads.")
    if len(FBI_FIELD_OFFICES) != 56:
        raise SystemExit(f"Expected 56 FBI field offices, found {len(FBI_FIELD_OFFICES)}.")
    source = Path(sys.argv[1])
    zips = load_zips(source)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUTPUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["zip", "city"])
        for code in sorted(zips):
            _state, lat, lon = zips[code]
            city = nearest_office(lat, lon)
            writer.writerow([code, city])
            written += 1
    print(f"Wrote {written} ZIP codes to {OUTPUT}")


def nearest_office(lat: float, lon: float) -> str:
    best_name = ""
    best_distance = math.inf
    for name, state, office_lat, office_lon in FBI_FIELD_OFFICES:
        distance = haversine_miles(lat, lon, office_lat, office_lon)
        if distance < best_distance:
            best_distance = distance
            best_name = f"{name}, {state}"
    return best_name


def choose_city(lat: float, lon: float, cities: list[tuple[str, float, float, int]]) -> str:
    """Nearest large city, with population pulling a major city ahead of a smaller neighbor."""
    for minimum in (LARGE_POPULATION, MEDIUM_POPULATION):
        pool = [city for city in cities if city[3] >= minimum]
        if pool:
            return highest_pull(lat, lon, pool)
    if not cities:
        return ""
    return highest_pull(lat, lon, cities)


def highest_pull(lat: float, lon: float, cities: list[tuple[str, float, float, int]]) -> str:
    best_name = ""
    best_score = -1.0
    for name, city_lat, city_lon, population in cities:
        distance = max(haversine_miles(lat, lon, city_lat, city_lon), 1.0)
        score = population / (distance * distance)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 3958.7613
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lon / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def load_zips(source: Path) -> dict[str, tuple[str, float, float]]:
    states = zip_states(source / "rel.txt")
    path = next((source / "zcta").glob("*.txt"))
    found: dict[str, tuple[str, float, float]] = {}
    for row in read_table(path, "\t"):
        code = row.get("GEOID", "")
        state = states.get(code)
        if not code.isdigit() or len(code) != 5 or not state:
            continue
        found[code] = (state, float(row["INTPTLAT"]), float(row["INTPTLONG"]))
    return found


def read_table(path: Path, delimiter: str) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle, delimiter=delimiter)
        header = [cell.strip() for cell in next(reader)]
        rows: list[dict[str, str]] = []
        for raw in reader:
            rows.append({header[index]: (raw[index].strip() if index < len(raw) else "") for index in range(len(header))})
    return rows


def zip_states(path: Path) -> dict[str, str]:
    best: dict[str, tuple[int, str]] = {}
    for row in read_table(path, "|"):
            code = (row.get("GEOID_ZCTA5_20") or "").strip()
            county = (row.get("GEOID_COUNTY_20") or "").strip()
            if len(code) != 5 or len(county) < 2:
                continue
            try:
                area = int(row.get("AREALAND_PART") or "0")
            except ValueError:
                area = 0
            state = county[:2]
            current = best.get(code)
            if current is None or area > current[0]:
                best[code] = (area, state)
    fips_to_usps = {f"{number:02d}": abbr for abbr, number in FIPS.items()}
    return {code: fips_to_usps[state] for code, (_area, state) in best.items() if state in fips_to_usps}


def load_cities(source: Path) -> list[tuple[str, str, float, float, int]]:
    coords: dict[str, tuple[float, float]] = {}
    path = next((source / "place").glob("*.txt"))
    for row in read_table(path, "\t"):
            geoid = (row.get("GEOID") or "").strip()
            if len(geoid) != 7:
                continue
            coords[geoid] = (float(row["INTPTLAT"]), float(row["INTPTLONG"]))
    cities: list[tuple[str, str, float, float, int]] = []
    with (source / "pop.csv").open(encoding="cp1252", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("SUMLEV") != "162":
                continue
            state_name = row.get("STNAME") or ""
            abbr = STATE_ABBR.get(state_name)
            if not abbr:
                continue
            geoid = f"{int(row['STATE']):02d}{row['PLACE']}"
            point = coords.get(geoid)
            if point is None:
                continue
            try:
                population = int(row["POPESTIMATE2024"])
            except ValueError:
                continue
            if population <= 0:
                continue
            cities.append((abbr, display_name(row.get("NAME") or ""), point[0], point[1], population))
    return cities


DISPLAY_NAMES = {"Urban Honolulu": "Honolulu"}


def display_name(name: str) -> str:
    cleaned = clean_name(name)
    return DISPLAY_NAMES.get(cleaned, cleaned)


def clean_name(name: str) -> str:
    folded = name.casefold()
    for suffix in NAME_SUFFIXES:
        if folded.endswith(suffix):
            return name[: -len(suffix)].strip()
    return name.strip()


FIPS = {
    "AL": 1,
    "AK": 2,
    "AZ": 4,
    "AR": 5,
    "CA": 6,
    "CO": 8,
    "CT": 9,
    "DE": 10,
    "DC": 11,
    "FL": 12,
    "GA": 13,
    "HI": 15,
    "ID": 16,
    "IL": 17,
    "IN": 18,
    "IA": 19,
    "KS": 20,
    "KY": 21,
    "LA": 22,
    "ME": 23,
    "MD": 24,
    "MA": 25,
    "MI": 26,
    "MN": 27,
    "MS": 28,
    "MO": 29,
    "MT": 30,
    "NE": 31,
    "NV": 32,
    "NH": 33,
    "NJ": 34,
    "NM": 35,
    "NY": 36,
    "NC": 37,
    "ND": 38,
    "OH": 39,
    "OK": 40,
    "OR": 41,
    "PA": 42,
    "RI": 44,
    "SC": 45,
    "SD": 46,
    "TN": 47,
    "TX": 48,
    "UT": 49,
    "VT": 50,
    "VA": 51,
    "WA": 53,
    "WV": 54,
    "WI": 55,
    "WY": 56,
    "PR": 72,
}


if __name__ == "__main__":
    main()
