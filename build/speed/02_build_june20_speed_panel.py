"""
Build the June 20 NYC OD-day speed panel.

This panel tests whether Citi Bike's operational June 20, 2025 e-bike speed
reduction changed average e-bike speed. The control group is classic-bike
rides within NYC, because classic bikes were not subject to the e-bike speed
cap.

Window:
    pre:  2025-05-23 through 2025-06-19
    post: 2025-06-20 through 2025-07-17

Rows are paired by origin-destination pair, ride type, week-within-window, and
day of week. The output row outcome is the post-minus-pre change in average
straight-line speed for that exact OD/type/day-position cell.
"""

from __future__ import annotations

import math
import zipfile
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data_raw" / "citi_bike"
OUT_DIR = PROJECT_ROOT / "data_clean" / "speed"
WEATHER_INPUT = PROJECT_ROOT / "data_clean" / "june_20" / "01_june_20_station_hour_panel_weather.csv"

RAW_FILES = (
    RAW_DIR / "202505-citibike-tripdata.zip",
    RAW_DIR / "202506-citibike-tripdata.zip",
    RAW_DIR / "202507-citibike-tripdata.zip",
)
PRE_START = pd.Timestamp("2025-05-23")
PRE_END = pd.Timestamp("2025-06-19 23:59:59.999999")
POST_START = pd.Timestamp("2025-06-20")
POST_END = pd.Timestamp("2025-07-17 23:59:59.999999")
MIN_TOTAL_RIDES_PER_TYPE = 50

USECOLS = [
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "start_station_id",
    "end_station_id",
    "start_lat",
    "start_lng",
    "end_lat",
    "end_lng",
]
WEATHER_CONTINUOUS = [
    "weather_temp_c",
    "weather_precip_mm",
    "weather_snow_mm",
    "weather_relative_humidity",
    "weather_wind_speed_kph",
]
WEATHER_COLUMNS = [*WEATHER_CONTINUOUS, "weather_weather_condition_code"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=int, default=MIN_TOTAL_RIDES_PER_TYPE)
    return parser.parse_args()


def haversine_miles(lat1: pd.Series, lng1: pd.Series, lat2: pd.Series, lng2: pd.Series) -> pd.Series:
    """Straight-line OD distance in miles."""

    radius_miles = 3958.7613
    lat1_rad = np.radians(lat1.astype(float))
    lng1_rad = np.radians(lng1.astype(float))
    lat2_rad = np.radians(lat2.astype(float))
    lng2_rad = np.radians(lng2.astype(float))
    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad
    a = np.sin(dlat / 2.0) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2.0) ** 2
    return radius_miles * 2 * np.arcsin(np.sqrt(a))


def write_csv_atomic(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(tmp, index=False)
    tmp.replace(path)


def read_speed_trips() -> tuple[pd.DataFrame, list[dict[str, object]]]:
    """Read trip files and apply ride-level validity filters for speed."""

    chunks: list[pd.DataFrame] = []
    diagnostics: list[dict[str, object]] = []
    for path in RAW_FILES:
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith(".csv") or member.lower().startswith("jc-"):
                    continue
                with archive.open(member) as handle:
                    for chunk in pd.read_csv(handle, usecols=USECOLS, chunksize=500_000, low_memory=False):
                        n_raw = len(chunk)
                        chunk["started_at"] = pd.to_datetime(chunk["started_at"], errors="coerce")
                        chunk["ended_at"] = pd.to_datetime(chunk["ended_at"], errors="coerce")

                        keep = chunk["started_at"].between(PRE_START, POST_END)
                        keep &= chunk["rideable_type"].isin(["electric_bike", "classic_bike"])
                        keep &= chunk["start_station_id"].notna() & chunk["end_station_id"].notna()
                        keep &= chunk["start_lat"].notna() & chunk["start_lng"].notna()
                        keep &= chunk["end_lat"].notna() & chunk["end_lng"].notna()
                        keep &= chunk["ended_at"].notna()
                        filtered = chunk.loc[keep, USECOLS].copy()

                        if filtered.empty:
                            diagnostics.append(
                                {
                                    "file": path.name,
                                    "raw_rows": n_raw,
                                    "window_and_column_valid_rows": 0,
                                    "speed_valid_rows": 0,
                                }
                            )
                            continue

                        filtered["duration_minutes"] = (
                            filtered["ended_at"] - filtered["started_at"]
                        ).dt.total_seconds() / 60.0
                        filtered["distance_miles"] = haversine_miles(
                            filtered["start_lat"],
                            filtered["start_lng"],
                            filtered["end_lat"],
                            filtered["end_lng"],
                        )
                        filtered["speed_mph"] = filtered["distance_miles"] / (filtered["duration_minutes"] / 60.0)

                        # These filters remove impossible or uninformative speed
                        # records while retaining ordinary short Citi Bike trips.
                        speed_valid = filtered["duration_minutes"].between(1, 180)
                        speed_valid &= filtered["distance_miles"].between(0.05, math.inf)
                        speed_valid &= filtered["speed_mph"].between(0.5, 30)
                        speed_trips = filtered.loc[speed_valid].copy()
                        chunks.append(speed_trips)
                        diagnostics.append(
                            {
                                "file": path.name,
                                "raw_rows": n_raw,
                                "window_and_column_valid_rows": len(filtered),
                                "speed_valid_rows": len(speed_trips),
                            }
                        )

    if not chunks:
        raise RuntimeError("No valid NYC speed trips found in the June 20 window.")

    trips = pd.concat(chunks, ignore_index=True)
    trips["date"] = trips["started_at"].dt.normalize()
    trips["period"] = np.where(trips["started_at"] < POST_START, "pre", "post")
    trips["window_start"] = np.where(trips["period"].eq("pre"), PRE_START, POST_START)
    trips["window_start"] = pd.to_datetime(trips["window_start"])
    trips["week_index"] = ((trips["date"] - trips["window_start"]).dt.days // 7 + 1).astype("int8")
    trips["day_of_week"] = trips["date"].dt.dayofweek.astype("int8")
    trips["od_pair"] = trips["start_station_id"].astype("string") + " -> " + trips["end_station_id"].astype("string")
    trips["station_uid"] = "nyc_od:" + trips["od_pair"].astype("string")
    return trips, diagnostics


def daily_weather() -> pd.DataFrame:
    """Create daily NYC weather controls from the existing June 20 weather panel."""

    usecols = ["city", "date", *WEATHER_COLUMNS]
    weather = pd.read_csv(WEATHER_INPUT, usecols=usecols, parse_dates=["date"], low_memory=False)
    weather = weather[weather["city"].eq("nyc")].copy()
    weather["weather_snow_mm"] = weather["weather_snow_mm"].fillna(0)

    # The station-hour weather file repeats the same city weather for every
    # retained station. Drop duplicates before aggregating to daily controls.
    weather = weather.drop_duplicates(["date", *WEATHER_COLUMNS])
    continuous = weather.groupby("date", as_index=False)[WEATHER_CONTINUOUS].mean()
    condition = (
        weather.groupby("date")["weather_weather_condition_code"]
        .agg(lambda s: s.mode(dropna=True).iloc[0] if not s.mode(dropna=True).empty else np.nan)
        .reset_index()
    )
    return continuous.merge(condition, on="date", how="left", validate="one_to_one")


def build_panel(trips: pd.DataFrame, threshold: int) -> tuple[pd.DataFrame, dict[str, object]]:
    """Aggregate speed by OD/type/day-position and create paired rows."""

    totals = (
        trips.groupby(["od_pair", "rideable_type"], as_index=False)
        .agg(total_rides=("ride_id", "count"))
        .pivot(index="od_pair", columns="rideable_type", values="total_rides")
        .fillna(0)
    )
    period_totals = (
        trips.groupby(["od_pair", "rideable_type", "period"], as_index=False)
        .agg(period_rides=("ride_id", "count"))
        .pivot_table(index="od_pair", columns=["rideable_type", "period"], values="period_rides", fill_value=0)
    )
    for col in [
        ("classic_bike", "pre"),
        ("classic_bike", "post"),
        ("electric_bike", "pre"),
        ("electric_bike", "post"),
    ]:
        if col not in period_totals.columns:
            period_totals[col] = 0

    eligible_pairs = totals[
        (totals.get("classic_bike", 0) >= threshold)
        & (totals.get("electric_bike", 0) >= threshold)
    ].index
    eligible_pairs = period_totals.loc[
        period_totals.index.isin(eligible_pairs)
        & (period_totals[("classic_bike", "pre")] > 0)
        & (period_totals[("classic_bike", "post")] > 0)
        & (period_totals[("electric_bike", "pre")] > 0)
        & (period_totals[("electric_bike", "post")] > 0)
    ].index

    daily = (
        trips[trips["od_pair"].isin(eligible_pairs)]
        .groupby(["station_uid", "od_pair", "rideable_type", "period", "week_index", "day_of_week"], as_index=False)
        .agg(
            date=("date", "first"),
            avg_speed_mph=("speed_mph", "mean"),
            ride_count=("ride_id", "count"),
            mean_duration_minutes=("duration_minutes", "mean"),
            mean_distance_miles=("distance_miles", "mean"),
        )
    )
    pre = daily[daily["period"].eq("pre")].rename(
        columns={
            "date": "date_t0",
            "avg_speed_mph": "y0",
            "ride_count": "ride_count_t0",
            "mean_duration_minutes": "mean_duration_minutes_t0",
            "mean_distance_miles": "mean_distance_miles_t0",
        }
    )
    post = daily[daily["period"].eq("post")].rename(
        columns={
            "date": "date_t1",
            "avg_speed_mph": "y1",
            "ride_count": "ride_count_t1",
            "mean_duration_minutes": "mean_duration_minutes_t1",
            "mean_distance_miles": "mean_distance_miles_t1",
        }
    )
    keys = ["station_uid", "od_pair", "rideable_type", "week_index", "day_of_week"]
    paired = pre.merge(
        post,
        on=keys,
        how="inner",
        suffixes=("_pre_unused", "_post_unused"),
        validate="one_to_one",
    )
    paired["A"] = paired["rideable_type"].eq("electric_bike").astype("int8")
    paired["city"] = paired["rideable_type"].map({"classic_bike": "classic_bike", "electric_bike": "electric_bike"})
    paired["system"] = "citibike_speed"
    paired["y_tilde"] = paired["y1"] - paired["y0"]

    weather = daily_weather()
    paired = paired.merge(weather.add_suffix("_t0"), left_on="date_t0", right_on="date_t0", how="left")
    paired = paired.merge(weather.add_suffix("_t1"), left_on="date_t1", right_on="date_t1", how="left")

    diagnostics = {
        "eligible_od_pairs": len(eligible_pairs),
        "threshold_min_total_rides_per_type": threshold,
        "paired_rows": len(paired),
        "classic_paired_rows": int((paired["A"] == 0).sum()),
        "ebike_paired_rows": int((paired["A"] == 1).sum()),
        "median_ride_count_t0": float(paired["ride_count_t0"].median()),
        "median_ride_count_t1": float(paired["ride_count_t1"].median()),
        "mean_y0": float(paired["y0"].mean()),
        "mean_y1": float(paired["y1"].mean()),
        "mean_y_tilde": float(paired["y_tilde"].mean()),
        "missing_weather_rows": int(paired[[f"{col}_t0" for col in WEATHER_COLUMNS] + [f"{col}_t1" for col in WEATHER_COLUMNS]].isna().any(axis=1).sum()),
    }
    return paired.sort_values(["rideable_type", "station_uid", "week_index", "day_of_week"]).reset_index(drop=True), diagnostics


def main() -> None:
    args = parse_args()
    trips, filter_diagnostics = read_speed_trips()
    panel, panel_diagnostics = build_panel(trips, args.threshold)

    panel_out = OUT_DIR / f"02_june20_speed_paired_panel_threshold{args.threshold}.csv"
    diagnostics_out = OUT_DIR / f"02_june20_speed_panel_diagnostics_threshold{args.threshold}.csv"

    diagnostics = pd.DataFrame(filter_diagnostics)
    diagnostics = pd.concat(
        [
            diagnostics,
            pd.DataFrame([{"file": "analysis_panel", **panel_diagnostics}]),
        ],
        ignore_index=True,
    )
    write_csv_atomic(panel, panel_out)
    write_csv_atomic(diagnostics, diagnostics_out)
    print(f"Wrote {len(panel):,} rows to {panel_out}")
    print(f"Wrote diagnostics to {diagnostics_out}")


if __name__ == "__main__":
    main()
