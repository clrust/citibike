"""
Build the sharp immediate-post station-hour panel.

This sensitivity treats the October 24, 2025 policy date as active beginning at
midnight. It compares the four weeks ending the day before implementation to
the four weeks beginning on the implementation date:

    pre:  2025-09-26 00:00 through 2025-10-23 23:00
    post: 2025-10-24 00:00 through 2025-11-20 23:00

Station retention is based on presence in both exact analysis windows.
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

import pandas as pd

from panel_utils import (
    PROJECT_ROOT,
    aggregate_file,
    build_panel,
    find_month_files,
    write_csv_atomic,
)


MONTHS = ["2025-09", "2025-10", "2025-11"]
EVENT_DATE = "2025-10-24"
SHARP_PRE = (pd.Timestamp("2025-09-26"), pd.Timestamp("2025-10-23 23:00:00"))
SHARP_POST = (pd.Timestamp("2025-10-24"), pd.Timestamp("2025-11-20 23:00:00"))
ANALYSIS_WINDOWS = [SHARP_PRE, SHARP_POST]
PANEL_OUT = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel.csv"
WEATHER_OUT = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weather-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather_filled_50km")
    return parser.parse_args()


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def in_analysis_windows(hours: pd.Series) -> pd.Series:
    mask = pd.Series(False, index=hours.index)
    for start, end in ANALYSIS_WINDOWS:
        mask |= hours.between(start, end)
    return mask


def build_city(config: dict) -> pd.DataFrame:
    raw_dirs = [PROJECT_ROOT / "data_raw" / config["raw_subdir"], PROJECT_ROOT / "data_raw"]
    files = find_month_files(raw_dirs, MONTHS, config["file_tokens"], config["exclude_prefixes"])

    aggregates: list[pd.DataFrame] = []
    stations: list[pd.DataFrame] = []
    for path in files:
        agg, station = aggregate_file(path, MONTHS, config["column_map"])
        if not agg.empty:
            aggregates.append(agg)
            stations.append(station)
    if not aggregates:
        raise RuntimeError(f"No trips remained for {config['system']} in {MONTHS}")

    panel = build_panel(
        pd.concat(aggregates, ignore_index=True),
        pd.concat(stations, ignore_index=True),
        MONTHS,
        config["city"],
        config["system"],
        config["treated_city"],
        EVENT_DATE,
        presence_windows=ANALYSIS_WINDOWS,
    )
    return panel.loc[in_analysis_windows(panel["station_hour"])].copy()


def main() -> None:
    args = parse_args()
    sensitivity_panels = load_module(PROJECT_ROOT / "build" / "09_build_sensitivity_panels.py", "sensitivity_panels")
    weather_merge = load_module(PROJECT_ROOT / "build" / "07_weather_merge.py", "weather_merge")

    pieces = [build_city(config) for config in sensitivity_panels.CITY_CONFIGS]
    panel = pd.concat(pieces, ignore_index=True)
    panel["station_hour"] = pd.to_datetime(panel["station_hour"], errors="coerce")
    panel = panel.sort_values(["city", "station_hour", "station_uid"]).reset_index(drop=True)

    write_csv_atomic(panel, PANEL_OUT)
    print(f"Wrote {len(panel):,} rows to {PANEL_OUT}")

    # Use exactly the requested weather directory so filled-weather runs cannot
    # accidentally merge against unfilled base weather files.
    merged = weather_merge.merge_weather(PANEL_OUT, [args.weather_dir], EVENT_DATE)
    write_csv_atomic(merged, WEATHER_OUT)
    print(f"Wrote {len(merged):,} weather rows to {WEATHER_OUT}")


if __name__ == "__main__":
    main()
