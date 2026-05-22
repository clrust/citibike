"""
Merge station-hour bike demand panels with hourly weather.

Inputs produced by:

    python3 build/01_citibike.py
    python3 build/02_divvy.py

Expected weather files can be CSVs under data_raw/weather/ or data_raw/ and
should contain an hourly timestamp plus weather covariates. The script accepts
common timestamp column names, including station_hour, datetime, time, date_time,
valid, and DATE. It writes both city-specific merged files and one combined
panel for DiD estimation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EVENT_DATE = "2025-10-24"
TIMESTAMP_CANDIDATES = ("station_hour", "datetime", "date_time", "time", "valid", "DATE", "date")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--citibike", type=Path, default=PROJECT_ROOT / "data_clean" / "citibike_station_hour.csv")
    parser.add_argument("--divvy", type=Path, default=PROJECT_ROOT / "data_clean" / "divvy_station_hour.csv")
    parser.add_argument("--weather-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather")
    parser.add_argument("--fallback-weather-dir", type=Path, default=PROJECT_ROOT / "data_raw")
    parser.add_argument("--nyc-weather", type=Path)
    parser.add_argument("--chicago-weather", type=Path)
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "data_clean")
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
    weather["weather_city"] = city
    return weather


def merge_city(panel_path: Path, weather_path: Path, city: str, event_date: str) -> pd.DataFrame:
    panel = pd.read_csv(panel_path, parse_dates=["station_hour"])
    weather = normalize_weather(weather_path, city)
    merged = panel.merge(weather, on="station_hour", how="left", validate="many_to_one")
    merged["post_speed_limit"] = (merged["station_hour"] >= pd.Timestamp(event_date)).astype("int8")
    merged["did_treated_post"] = merged["treated_city"] * merged["post_speed_limit"]
    return merged


def main() -> None:
    args = parse_args()
    nyc_weather = args.nyc_weather or find_weather_file([args.weather_dir, args.fallback_weather_dir], ("nyc", "new_york", "new-york", "central_park", "laguardia", "jfk"))
    chicago_weather = args.chicago_weather or find_weather_file([args.weather_dir, args.fallback_weather_dir], ("chicago", "ord", "midway", "ohare", "o'hare"))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    citibike = merge_city(args.citibike, nyc_weather, "nyc", args.event_date)
    divvy = merge_city(args.divvy, chicago_weather, "chicago", args.event_date)

    citibike_out = args.out_dir / "citibike_station_hour_weather.csv"
    divvy_out = args.out_dir / "divvy_station_hour_weather.csv"
    combined_out = args.out_dir / "did_station_hour_weather.csv"
    citibike.to_csv(citibike_out, index=False)
    divvy.to_csv(divvy_out, index=False)
    pd.concat([citibike, divvy], ignore_index=True).to_csv(combined_out, index=False)

    print(f"Wrote {len(citibike):,} Citi Bike rows to {citibike_out}")
    print(f"Wrote {len(divvy):,} Divvy rows to {divvy_out}")
    print(f"Wrote combined DiD panel to {combined_out}")


if __name__ == "__main__":
    main()
