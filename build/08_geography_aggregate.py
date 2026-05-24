"""
Aggregate station-hour panels to geography-hour panels.

Use --crosswalk for official neighborhood/community-area labels with columns:
city,start_station_id,geography

Without a crosswalk, the script builds a consistent latitude/longitude grid
from station coordinates. This is useful as a compute-friendly sensitivity,
but official neighborhood polygons are preferable for final reporting.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--panel", type=Path, default=PROJECT_ROOT / "data_clean" / "07_station_hour_panel_weather.csv")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data_clean" / "08_geography_hour_panel.csv")
    parser.add_argument("--crosswalk", type=Path)
    parser.add_argument("--geography-column", default="geography")
    parser.add_argument("--grid-decimals", type=int, default=2)
    return parser.parse_args()


def add_geography(panel: pd.DataFrame, args: argparse.Namespace) -> pd.DataFrame:
    panel = panel.copy()
    if args.crosswalk:
        crosswalk = pd.read_csv(args.crosswalk, dtype={"start_station_id": "string"})
        station_key = "station_uid" if "station_uid" in crosswalk.columns else "start_station_id"
        required = {"city", station_key, args.geography_column}
        missing = required.difference(crosswalk.columns)
        if missing:
            raise ValueError(f"Crosswalk is missing required columns: {sorted(missing)}")
        crosswalk = crosswalk.loc[:, ["city", station_key, args.geography_column]].drop_duplicates()
        panel["start_station_id"] = panel["start_station_id"].astype("string")
        if station_key == "station_uid" and "station_uid" not in panel.columns:
            panel["station_uid"] = panel["city"].astype(str) + ":" + panel["start_station_id"].astype(str)
        panel = panel.merge(crosswalk, on=["city", station_key], how="left", validate="many_to_one")
        panel["geography"] = panel[args.geography_column].fillna("unknown")
        return panel

    lat = pd.to_numeric(panel["start_lat"], errors="coerce").round(args.grid_decimals)
    lng = pd.to_numeric(panel["start_lng"], errors="coerce").round(args.grid_decimals)
    panel["geography"] = panel["city"].astype(str) + "_grid_" + lat.astype("string") + "_" + lng.astype("string")
    panel["geography"] = panel["geography"].fillna(panel["city"].astype(str) + "_grid_unknown")
    return panel


def aggregate(panel: pd.DataFrame) -> pd.DataFrame:
    group_cols = ["city", "system", "geography", "station_hour"]
    first_cols = [
        "treated_city",
        "post_speed_limit",
        "month",
        "date",
        "hour",
        "day_of_week",
        "did_treated_post",
    ]
    weather_cols = [col for col in panel.columns if col.startswith("weather_")]
    agg_spec = {
        "trip_count": ("trip_count", "sum"),
        "ebike_trip_count": ("ebike_trip_count", "sum"),
        "classic_trip_count": ("classic_trip_count", "sum"),
        "mean_duration_minutes": ("mean_duration_minutes", "mean"),
        "station_count": ("station_uid" if "station_uid" in panel.columns else "start_station_id", "nunique"),
        "start_lat": ("start_lat", "mean"),
        "start_lng": ("start_lng", "mean"),
    }
    for col in first_cols + weather_cols:
        if col in panel.columns:
            agg_spec[col] = (col, "first")
    return panel.groupby(group_cols, dropna=False).agg(**agg_spec).reset_index()


def main() -> None:
    args = parse_args()
    panel = pd.read_csv(args.panel, parse_dates=["station_hour"], low_memory=False)
    panel = add_geography(panel, args)
    geography = aggregate(panel)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    geography.to_csv(args.out, index=False)
    print(f"Wrote {len(geography):,} geography-hour rows to {args.out}")


if __name__ == "__main__":
    main()
