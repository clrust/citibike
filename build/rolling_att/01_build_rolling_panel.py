"""
Build the broad Aug-Nov 2025 station-hour panel for rolling ATT plots.

The rolling analysis evaluates multiple assumed treatment dates around the
October 24 policy date. This build writes one broad panel covering all hours
needed by those rolling four-week pre/post windows:

    broad range: 2025-07-18 00:00 through 2025-11-27 23:00

Station retention for each assumed treatment date is handled later in the
analysis script. Here, a station only needs to appear at least once in the
broad range so the analysis has enough raw material to apply date-specific
retention rules.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

import pandas as pd


BUILD_ROOT = Path(__file__).resolve().parents[1]
if str(BUILD_ROOT) not in sys.path:
    sys.path.insert(0, str(BUILD_ROOT))

from panel_utils import (  # noqa: E402
    PROJECT_ROOT,
    aggregate_file,
    build_panel,
    find_month_files,
    write_csv_atomic,
)


MONTHS = ["2025-07", "2025-08", "2025-09", "2025-10", "2025-11"]
BROAD_START = pd.Timestamp("2025-07-18")
BROAD_END = pd.Timestamp("2025-11-27 23:00:00")
PANEL_OUT = PROJECT_ROOT / "data_clean" / "rolling_att" / "01_rolling_station_hour_panel.csv"
WEATHER_OUT = PROJECT_ROOT / "data_clean" / "rolling_att" / "01_rolling_station_hour_panel_weather.csv"


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
        "2025-10-24",
        presence_windows=[(BROAD_START, BROAD_END)],
    )
    return panel.loc[panel["station_hour"].between(BROAD_START, BROAD_END)].copy()


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

    merged = weather_merge.merge_weather(PANEL_OUT, [args.weather_dir], "2025-10-24")
    write_csv_atomic(merged, WEATHER_OUT)
    print(f"Wrote {len(merged):,} weather rows to {WEATHER_OUT}")


if __name__ == "__main__":
    main()
