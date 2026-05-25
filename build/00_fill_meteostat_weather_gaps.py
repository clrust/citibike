"""
Fill missing hourly weather values from nearby Meteostat stations.

Primary station observations remain authoritative. This script only fills
missing non-snow weather values from alternate stations within a capped radius
and writes filled copies to a separate directory for audit before adoption.
"""

from __future__ import annotations

import argparse
from datetime import timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from panel_utils import PROJECT_ROOT, write_csv_atomic


CITY_CONFIGS = {
    "nyc": {
        "latitude": 40.7829,
        "longitude": -73.9654,
        "timezone": "America/New_York",
        "file": "nyc_weather.csv",
    },
    "chicago": {
        "latitude": 41.9742,
        "longitude": -87.9073,
        "timezone": "America/Chicago",
        "file": "chicago_weather.csv",
    },
    "philadelphia": {
        "latitude": 39.8729,
        "longitude": -75.2437,
        "timezone": "America/New_York",
        "file": "philadelphia_weather.csv",
    },
    "boston": {
        "latitude": 42.3656,
        "longitude": -71.0096,
        "timezone": "America/New_York",
        "file": "boston_weather.csv",
    },
    "washington_dc": {
        "latitude": 38.8512,
        "longitude": -77.0402,
        "timezone": "America/New_York",
        "file": "washington_dc_weather.csv",
    },
}

FILL_COLUMNS = (
    "temp_c",
    "relative_humidity",
    "precip_mm",
    "wind_speed_kph",
    "weather_condition_code",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weather-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather")
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather_filled_20km")
    parser.add_argument("--cache-dir", type=Path, default=PROJECT_ROOT / ".meteostat_cache")
    parser.add_argument("--radius-km", type=float, default=20)
    parser.add_argument("--limit", type=int, default=25)
    return parser.parse_args()


def utc_bounds(weather: pd.DataFrame, local_timezone: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    tz = ZoneInfo(local_timezone)
    start = pd.to_datetime(weather["station_hour"].min()).replace(tzinfo=tz)
    end = pd.to_datetime(weather["station_hour"].max()).replace(tzinfo=tz)
    return (
        start.astimezone(timezone.utc).replace(tzinfo=None),
        end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def nearby_station_ids(config: dict, radius_km: float, limit: int) -> pd.DataFrame:
    from meteostat import Point, stations

    nearby = stations.nearby(
        Point(config["latitude"], config["longitude"]),
        radius=radius_km * 1000,
        limit=limit,
    )
    if nearby.empty:
        return nearby
    return nearby.sort_values("distance")


def normalize_alternate_weather(station_id: str, start_utc: pd.Timestamp, end_utc: pd.Timestamp, local_timezone: str) -> pd.DataFrame:
    from meteostat import hourly

    fetched = hourly(station_id, start_utc.to_pydatetime(), end_utc.to_pydatetime()).fetch()
    if fetched is None or fetched.empty:
        return pd.DataFrame(columns=["station_hour", *FILL_COLUMNS])

    weather = fetched.reset_index()
    weather["station_hour"] = (
        pd.to_datetime(weather["time"], utc=True)
        .dt.tz_convert(ZoneInfo(local_timezone))
        .dt.tz_localize(None)
    )
    weather = weather.rename(
        columns={
            "temp": "temp_c",
            "rhum": "relative_humidity",
            "prcp": "precip_mm",
            "wspd": "wind_speed_kph",
            "coco": "weather_condition_code",
        }
    )
    keep = ["station_hour", *[col for col in FILL_COLUMNS if col in weather.columns]]
    return weather.loc[:, keep].groupby("station_hour", as_index=False).first()


def fill_city(city: str, args: argparse.Namespace) -> pd.DataFrame:
    config = CITY_CONFIGS[city]
    path = args.weather_dir / config["file"]
    weather = pd.read_csv(path, parse_dates=["station_hour"], low_memory=False)
    filled = weather.copy()
    diagnostics: list[dict] = []

    start_utc, end_utc = utc_bounds(weather, config["timezone"])
    candidates = nearby_station_ids(config, args.radius_km, args.limit)
    primary_station = str(weather["weather_station_id"].dropna().iloc[0]) if weather["weather_station_id"].notna().any() else ""

    before_missing = weather.loc[:, FILL_COLUMNS].isna().sum()
    for station_id, station_meta in candidates.iterrows():
        station_id = str(station_id)
        if station_id == primary_station:
            continue
        remaining = filled.loc[:, FILL_COLUMNS].isna().sum()
        if int(remaining.sum()) == 0:
            break

        alternate = normalize_alternate_weather(station_id, start_utc, end_utc, config["timezone"])
        if alternate.empty:
            continue
        alternate = alternate.set_index("station_hour")
        aligned = filled[["station_hour"]].join(alternate, on="station_hour", rsuffix="_alternate")

        for col in FILL_COLUMNS:
            if col not in aligned:
                continue
            mask = filled[col].isna() & aligned[col].notna()
            n_filled = int(mask.sum())
            if n_filled == 0:
                continue
            filled.loc[mask, col] = aligned.loc[mask, col]
            diagnostics.append(
                {
                    "city": city,
                    "column": col,
                    "fill_station_id": station_id,
                    "fill_station_name": station_meta.get("name"),
                    "fill_station_distance_km": station_meta.get("distance", pd.NA) / 1000,
                    "n_hours_filled": n_filled,
                }
            )

    if "temp_c" in filled:
        filled["temp_f"] = filled["temp_c"] * 9 / 5 + 32
    if "precip_mm" in filled:
        filled["precip_in"] = filled["precip_mm"] / 25.4
    if "wind_speed_kph" in filled:
        filled["wind_speed_mph"] = filled["wind_speed_kph"] * 0.621371

    out_path = args.out_dir / config["file"]
    write_csv_atomic(filled, out_path)

    after_missing = filled.loc[:, FILL_COLUMNS].isna().sum()
    summary = pd.DataFrame(
        {
            "city": city,
            "column": list(FILL_COLUMNS),
            "missing_before": [int(before_missing[col]) for col in FILL_COLUMNS],
            "missing_after": [int(after_missing[col]) for col in FILL_COLUMNS],
            "hours_filled": [int(before_missing[col] - after_missing[col]) for col in FILL_COLUMNS],
        }
    )
    detail = pd.DataFrame(diagnostics)
    if not detail.empty:
        detail = detail.groupby(["city", "column", "fill_station_id", "fill_station_name", "fill_station_distance_km"], as_index=False)[
            "n_hours_filled"
        ].sum()
    detail_path = args.out_dir / f"{city}_weather_fill_detail.csv"
    write_csv_atomic(detail, detail_path)
    return summary


def main() -> None:
    args = parse_args()
    from meteostat.api.config import config

    args.cache_dir.mkdir(parents=True, exist_ok=True)
    config.cache_directory = str(args.cache_dir / "cache")
    config.stations_db_file = str(args.cache_dir / "stations.db")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summaries = [fill_city(city, args) for city in CITY_CONFIGS]
    summary = pd.concat(summaries, ignore_index=True)
    summary_path = args.out_dir / "weather_fill_summary.csv"
    write_csv_atomic(summary, summary_path)
    print(summary.to_string(index=False))
    print(f"Wrote filled weather files and diagnostics to {args.out_dir}")


if __name__ == "__main__":
    main()
