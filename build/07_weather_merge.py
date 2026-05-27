"""
Merge station-hour bike demand panels with hourly weather.

Expected weather files can be CSVs under data_raw/weather/ or data_raw/ and
should contain an hourly timestamp plus weather covariates. The script accepts
common timestamp column names, including station_hour, datetime, time, date_time,
valid, and DATE.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from panel_utils import write_csv_atomic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENT_DATE = "2025-10-24"
TIMESTAMP_CANDIDATES = ("station_hour", "datetime", "date_time", "time", "valid", "DATE", "date")
WEATHER_TOKENS = {
    "nyc": ("nyc", "new_york", "new-york", "central_park", "laguardia", "jfk"),
    "chicago": ("chicago", "ord", "midway", "ohare", "o'hare"),
    "philadelphia": ("philadelphia", "philly", "phl"),
    "boston": ("boston", "bos", "logan"),
    "washington_dc": ("washington_dc", "washington", "dc", "dca"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--panel",
        type=Path,
        default=PROJECT_ROOT / "data_clean" / "og_main_spec_sept_nov" / "06_station_hour_panel.csv",
    )
    parser.add_argument("--weather-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather")
    parser.add_argument("--fallback-weather-dir", type=Path, default=PROJECT_ROOT / "data_raw")
    parser.add_argument(
        "--out",
        type=Path,
        default=PROJECT_ROOT / "data_clean" / "og_main_spec_sept_nov" / "07_station_hour_panel_weather.csv",
    )
    parser.add_argument("--event-date", default=DEFAULT_EVENT_DATE)
    return parser.parse_args()


def find_weather_file(weather_dirs: list[Path], city_tokens: tuple[str, ...]) -> Path:
    matches: list[Path] = []
    for weather_dir in weather_dirs:
        if not weather_dir.exists():
            continue
        for path in weather_dir.rglob("*.csv"):
            name = path.name.lower()
            if any(token in name for token in city_tokens) and "weather" in name:
                matches.append(path)
        for path in weather_dir.rglob("*.csv"):
            name = path.name.lower()
            if any(token in name for token in city_tokens) and path not in matches:
                matches.append(path)
    if not matches:
        searched = ", ".join(str(d) for d in weather_dirs)
        raise FileNotFoundError(f"No weather CSV found for tokens {city_tokens} in {searched}")
    return sorted(matches)[0]


def normalize_weather(path: Path, city: str) -> pd.DataFrame:
    weather = pd.read_csv(path, low_memory=False)
    weather = weather.rename(columns={c: c.strip() for c in weather.columns})
    timestamp_col = next((c for c in TIMESTAMP_CANDIDATES if c in weather.columns), None)
    if timestamp_col is None:
        lower_lookup = {c.lower(): c for c in weather.columns}
        timestamp_col = next((lower_lookup[c.lower()] for c in TIMESTAMP_CANDIDATES if c.lower() in lower_lookup), None)
    if timestamp_col is None:
        raise ValueError(f"No hourly timestamp column found in {path}")

    weather["station_hour"] = pd.to_datetime(weather[timestamp_col], errors="coerce").dt.floor("h")
    drop_cols = [] if timestamp_col == "station_hour" else [timestamp_col]
    weather = weather.dropna(subset=["station_hour"]).drop(columns=drop_cols, errors="ignore")
    weather.columns = [
        "station_hour" if c == "station_hour" else f"weather_{c.strip().lower().replace(' ', '_')}"
        for c in weather.columns
    ]

    duplicate_cols = [c for c in weather.columns if c != "station_hour" and c.startswith("weather_station_hour")]
    weather = weather.drop(columns=duplicate_cols, errors="ignore")
    weather = weather.groupby("station_hour", as_index=False).first()
    weather["city"] = city
    return weather


def merge_weather(panel_path: Path, weather_dirs: list[Path], event_date: str) -> pd.DataFrame:
    panel = pd.read_csv(panel_path, parse_dates=["station_hour"], low_memory=False)
    weather_pieces = []
    for city in sorted(panel["city"].dropna().unique()):
        if city not in WEATHER_TOKENS:
            raise ValueError(f"No weather token config for city={city}")
        weather_path = find_weather_file(weather_dirs, WEATHER_TOKENS[city])
        weather_pieces.append(normalize_weather(weather_path, city))
    weather = pd.concat(weather_pieces, ignore_index=True)
    merged = panel.merge(weather, on=["city", "station_hour"], how="left", validate="many_to_one")
    merged["post_speed_limit"] = (merged["station_hour"] >= pd.Timestamp(event_date)).astype("int8")
    merged["did_treated_post"] = merged["treated_city"] * merged["post_speed_limit"]
    return merged


def main() -> None:
    args = parse_args()
    merged = merge_weather(args.panel, [args.weather_dir, args.fallback_weather_dir], args.event_date)
    write_csv_atomic(merged, args.out)
    print(f"Wrote {len(merged):,} station-hour weather rows to {args.out}")


if __name__ == "__main__":
    main()
