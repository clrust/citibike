"""
Build station-hour weather panels for placebo/sensitivity periods.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pandas as pd

from panel_utils import PROJECT_ROOT, aggregate_file, build_panel, find_month_files, write_csv_atomic


CITY_CONFIGS = (
    {
        "city": "nyc",
        "system": "citibike",
        "raw_subdir": "citi_bike",
        "file_tokens": ("citibike",),
        "exclude_prefixes": ("jc-",),
        "treated_city": 1,
        "column_map": {
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
    },
    {
        "city": "chicago",
        "system": "divvy",
        "raw_subdir": "divvy",
        "file_tokens": ("divvy",),
        "exclude_prefixes": (),
        "treated_city": 0,
        "column_map": {
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
    },
    {
        "city": "philadelphia",
        "system": "indego",
        "raw_subdir": "indego",
        "file_tokens": ("indego",),
        "exclude_prefixes": (),
        "treated_city": 0,
        "column_map": {
            "start_time": "started_at",
            "end_time": "ended_at",
            "bike_type": "rideable_type",
            "start_station": "start_station_id",
            "start_lat": "start_lat",
            "start_lon": "start_lng",
            "duration": "duration_minutes",
        },
    },
    {
        "city": "boston",
        "system": "bluebikes",
        "raw_subdir": "bluebike",
        "file_tokens": ("bluebike", "bluebikes"),
        "exclude_prefixes": (),
        "treated_city": 0,
        "column_map": {
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
    },
    {
        "city": "washington_dc",
        "system": "capital_bikeshare",
        "raw_subdir": "capitalbike",
        "file_tokens": ("capitalbikeshare", "capitalbike"),
        "exclude_prefixes": (),
        "treated_city": 0,
        "column_map": {
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
    },
)

SCENARIOS = {
    "2025_aug_sep": {
        "months": ["2025-08", "2025-09"],
        "panel_out": PROJECT_ROOT / "data_clean" / "sensitivities" / "2025_aug_sep_station_hour_panel.csv",
        "weather_out": PROJECT_ROOT / "data_clean" / "sensitivities" / "2025_aug_sep_station_hour_panel_weather.csv",
    },
    "2024_sep_nov": {
        "months": ["2024-09", "2024-11"],
        "panel_out": PROJECT_ROOT / "data_clean" / "sensitivities" / "2024_sep_nov_station_hour_panel.csv",
        "weather_out": PROJECT_ROOT / "data_clean" / "sensitivities" / "2024_sep_nov_station_hour_panel_weather.csv",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), action="append")
    parser.add_argument("--weather-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather")
    return parser.parse_args()


def load_weather_merge_module():
    path = PROJECT_ROOT / "build" / "07_weather_merge.py"
    spec = importlib.util.spec_from_file_location("weather_merge", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_city(config: dict, months: list[str]) -> pd.DataFrame:
    raw_dirs = [PROJECT_ROOT / "data_raw" / config["raw_subdir"], PROJECT_ROOT / "data_raw"]
    files = find_month_files(raw_dirs, months, config["file_tokens"], config["exclude_prefixes"])
    aggregates: list[pd.DataFrame] = []
    stations: list[pd.DataFrame] = []
    for path in files:
        agg, station = aggregate_file(path, months, config["column_map"])
        if not agg.empty:
            aggregates.append(agg)
            stations.append(station)
    if not aggregates:
        raise RuntimeError(f"No trips remained for {config['system']} in {months}")
    return build_panel(
        pd.concat(aggregates, ignore_index=True),
        pd.concat(stations, ignore_index=True),
        months,
        config["city"],
        config["system"],
        config["treated_city"],
        "2025-10-24",
    )


def build_scenario(name: str, weather_dir: Path) -> None:
    scenario = SCENARIOS[name]
    months = scenario["months"]
    pieces = [build_city(config, months) for config in CITY_CONFIGS]
    panel = pd.concat(pieces, ignore_index=True)
    panel["station_hour"] = pd.to_datetime(panel["station_hour"], errors="coerce")
    panel = panel.sort_values(["city", "station_hour", "station_uid"]).reset_index(drop=True)

    panel_out = scenario["panel_out"]
    weather_out = scenario["weather_out"]
    write_csv_atomic(panel, panel_out)
    print(f"Wrote {len(panel):,} rows to {panel_out}")

    weather_merge = load_weather_merge_module()
    merged = weather_merge.merge_weather(panel_out, [weather_dir, PROJECT_ROOT / "data_raw"], "2025-10-24")
    write_csv_atomic(merged, weather_out)
    print(f"Wrote {len(merged):,} weather rows to {weather_out}")


def main() -> None:
    args = parse_args()
    scenarios = args.scenario or sorted(SCENARIOS)
    for scenario in scenarios:
        build_scenario(scenario, args.weather_dir)


if __name__ == "__main__":
    main()
