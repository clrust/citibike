"""
Build the sharp-window city-hour e-bike share panel.

This aggregates the preferred sharp station-hour main-spec panel to city-hours.
The resulting file is the clean input for the e-bike share AIPTW sensitivity.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from panel_utils import PROJECT_ROOT, write_csv_atomic


INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"
OUT_PATH = PROJECT_ROOT / "data_clean" / "sensitivities" / "13_sharp_ebike_share_city_hour.csv"
T0_START = pd.Timestamp("2025-09-26")
T0_END = pd.Timestamp("2025-10-23 23:00:00")
T1_START = pd.Timestamp("2025-10-24")
T1_END = pd.Timestamp("2025-11-20 23:00:00")
CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
WEATHER_COLUMNS = (
    "weather_temp_c",
    "weather_precip_mm",
    "weather_snow_mm",
    "weather_relative_humidity",
    "weather_wind_speed_kph",
    "weather_weather_condition_code",
)


def add_window_keys(df: pd.DataFrame, start: pd.Timestamp, period: str) -> pd.DataFrame:
    """Add analysis-window labels and pairing keys before aggregation."""

    out = df.copy()
    out["period"] = period
    out["week_index"] = ((out["station_hour"].dt.normalize() - start).dt.days // 7 + 1).astype("int8")
    out["day_of_week"] = out["station_hour"].dt.dayofweek.astype("int8")
    out["hour"] = out["station_hour"].dt.hour.astype("int8")
    return out


def build_city_hour_panel(input_path: Path = INPUT_PATH) -> pd.DataFrame:
    usecols = ["city", "station_hour", "ebike_trip_count", "classic_trip_count", *WEATHER_COLUMNS]
    panel = pd.read_csv(input_path, usecols=usecols, parse_dates=["station_hour"], low_memory=False)
    panel = panel[panel["city"].isin(("nyc", *CONTROLS))].copy()

    pre = add_window_keys(panel[panel["station_hour"].between(T0_START, T0_END)], T0_START, "pre")
    post = add_window_keys(panel[panel["station_hour"].between(T1_START, T1_END)], T1_START, "post")
    panel = pd.concat([pre, post], ignore_index=True)

    agg_spec = {
        "ebike_trip_count": "sum",
        "classic_trip_count": "sum",
    }
    for col in WEATHER_COLUMNS:
        agg_spec[col] = "first"
    city_hour = (
        panel.groupby(["period", "city", "station_hour", "week_index", "day_of_week", "hour"], as_index=False)
        .agg(agg_spec)
        .sort_values(["period", "city", "station_hour"])
        .reset_index(drop=True)
    )
    city_hour["total_trip_count"] = city_hour["ebike_trip_count"] + city_hour["classic_trip_count"]
    if city_hour["total_trip_count"].eq(0).any():
        raise RuntimeError("Found city-hours with zero total trips; e-bike share is undefined.")
    city_hour["ebike_share"] = city_hour["ebike_trip_count"] / city_hour["total_trip_count"]
    city_hour["weather_snow_mm"] = city_hour["weather_snow_mm"].fillna(0)
    return city_hour


def main() -> None:
    city_hour = build_city_hour_panel()
    write_csv_atomic(city_hour, OUT_PATH)
    print(f"Wrote {len(city_hour):,} city-hour rows to {OUT_PATH}")


if __name__ == "__main__":
    main()
