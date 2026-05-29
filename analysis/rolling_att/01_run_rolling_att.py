"""
Run rolling assumed-treatment-date AIPTW estimates.

Each candidate date is treated as if the October policy started on that day.
For date d, the analysis uses the four weeks ending the hour before d as t0 and
the four weeks starting at d as t1. Outcome: ebike_trip_count at the paired
station-hour level. X covariates: paired differences in continuous weather
variables, pre/post coarse weather-condition indicators, and categorical hour,
day_of_week, and week_index indicators.

For each assumed date, stations are retained only if they have at least one
observed trip in that date's exact pre window and at least one observed trip in
that date's exact post window.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

from aiptw_common import (  # noqa: E402
    PROJECT_ROOT,
    WEATHER_CONTINUOUS,
    analysis_window_with_pairing_keys,
    city_diagnostics,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
    weather_category,
)


INPUT_PATH = PROJECT_ROOT / "data_clean" / "rolling_att" / "01_rolling_station_hour_panel_weather.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "rolling_att"
DATE_LEVEL_DIR = RESULTS_DIR / "date_level"
SUMMARY_OUT = RESULTS_DIR / "rolling_att_summary.csv"
ASSUMED_DATES = (
    "2025-08-15",
    "2025-08-22",
    "2025-08-29",
    "2025-09-05",
    "2025-09-12",
    "2025-09-19",
    "2025-09-26",
    "2025-10-03",
    "2025-10-10",
    "2025-10-17",
    "2025-10-24",
    "2025-10-31",
)
USECOLS = [
    "station_uid",
    "city",
    "system",
    "station_hour",
    "trip_count",
    "ebike_trip_count",
    "weather_temp_c",
    "weather_precip_mm",
    "weather_snow_mm",
    "weather_relative_humidity",
    "weather_wind_speed_kph",
    "weather_weather_condition_code",
]


def windows_for_date(date: str) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]:
    assumed = pd.Timestamp(date)
    t0_start = assumed - pd.Timedelta(days=28)
    t0_end = assumed - pd.Timedelta(hours=1)
    t1_start = assumed
    t1_end = assumed + pd.Timedelta(days=28) - pd.Timedelta(hours=1)
    return t0_start, t0_end, t1_start, t1_end


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dates",
        nargs="+",
        default=list(ASSUMED_DATES),
        help="Assumed treatment dates to estimate. The combined summary is rebuilt from all available date results.",
    )
    return parser.parse_args()


def retained_stations(panel: pd.DataFrame, t0_start: pd.Timestamp, t0_end: pd.Timestamp, t1_start: pd.Timestamp, t1_end: pd.Timestamp) -> set[str]:
    """Return stations with observed activity in both exact rolling windows."""

    t0_active = panel.loc[
        panel["station_hour"].between(t0_start, t0_end) & (panel["trip_count"] > 0),
        "station_uid",
    ].drop_duplicates()
    t1_active = panel.loc[
        panel["station_hour"].between(t1_start, t1_end) & (panel["trip_count"] > 0),
        "station_uid",
    ].drop_duplicates()
    return set(t0_active).intersection(set(t1_active))


def build_paired_for_date(panel: pd.DataFrame, config) -> tuple[pd.DataFrame, list[str]]:
    """Create a paired dataset after date-specific station retention."""

    keep = retained_stations(panel, config.t0_start, config.t0_end, config.t1_start, config.t1_end)
    if not keep:
        raise RuntimeError(f"No retained stations for assumed date {config.t1_start.date()}")

    work = panel[panel["station_uid"].isin(keep)].copy()
    work["weather_snow_mm"] = work["weather_snow_mm"].fillna(0)

    keys = ["station_uid", "week_index", "day_of_week", "hour"]
    meta_cols = ["station_uid", "city", "system", "week_index", "day_of_week", "hour"]
    weather_cols = list(WEATHER_CONTINUOUS.values()) + ["weather_weather_condition_code"]

    t0 = analysis_window_with_pairing_keys(work, config.t0_start, config.t0_end)
    t1 = analysis_window_with_pairing_keys(work, config.t1_start, config.t1_end)
    t0 = t0.loc[:, meta_cols + [config.outcome_col, "station_hour"] + weather_cols].rename(
        columns={config.outcome_col: "y0", "station_hour": "station_hour_t0"}
    )
    t1 = t1.loc[:, keys + [config.outcome_col, "station_hour"] + weather_cols].rename(
        columns={config.outcome_col: "y1", "station_hour": "station_hour_t1"}
    )

    paired = t0.merge(t1, on=keys, how="inner", suffixes=("_t0", "_t1"), validate="one_to_one")
    paired["A"] = (paired["city"] == config.treated_city).astype("int8")
    paired["y_tilde"] = paired["y1"] - paired["y0"]

    feature_cols: list[str] = []
    for feature_name, col in WEATHER_CONTINUOUS.items():
        out_col = f"delta_{feature_name}"
        paired[out_col] = paired[f"{col}_t1"] - paired[f"{col}_t0"]
        feature_cols.append(out_col)

    paired["condition_t0"] = paired["weather_weather_condition_code_t0"].map(weather_category)
    paired["condition_t1"] = paired["weather_weather_condition_code_t1"].map(weather_category)
    condition_dummies = pd.get_dummies(
        paired[["condition_t0", "condition_t1"]],
        columns=["condition_t0", "condition_t1"],
        prefix=["condition_t0", "condition_t1"],
        dtype="int8",
    )
    time_dummies = pd.get_dummies(
        paired[["hour", "day_of_week", "week_index"]],
        columns=["hour", "day_of_week", "week_index"],
        prefix=["hour", "day_of_week", "week_index"],
        dtype="int8",
    )
    paired = pd.concat([paired, condition_dummies, time_dummies], axis=1)
    feature_cols.extend(condition_dummies.columns.to_list())
    feature_cols.extend(time_dummies.columns.to_list())
    return paired.sort_values(["city", "station_uid", "week_index", "day_of_week", "hour"]).reset_index(drop=True), feature_cols


def run_one_date(panel: pd.DataFrame, date: str) -> pd.DataFrame:
    t0_start, t0_end, t1_start, t1_end = windows_for_date(date)
    config = make_config(
        estimand=f"NYC rolling sharp-window ATT assuming treatment on {date} (row-weighted)",
        station_weighted=False,
        input_path=INPUT_PATH,
        results_dir=DATE_LEVEL_DIR,
        output_stem=f"rolling_att_{date}",
        t0_start=str(t0_start),
        t0_end=str(t0_end),
        t1_start=str(t1_start),
        t1_end=str(t1_end),
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    paired, feature_cols = build_paired_for_date(panel, config)
    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    result, estimated = estimate_att(predictions, config)
    diagnostics = city_diagnostics(estimated, config)
    result["assumed_treatment_date"] = date
    result["retention_rule"] = "station active in both exact rolling windows"

    result.to_csv(config.result_path, index=False)
    diagnostics.to_csv(config.diagnostics_path, index=False)
    return result


def rebuild_summary() -> pd.DataFrame:
    rows = []
    for date in ASSUMED_DATES:
        path = DATE_LEVEL_DIR / f"rolling_att_{date}.csv"
        if path.exists():
            result = pd.read_csv(path)
            result["assumed_treatment_date"] = date
            rows.append(result)
    if not rows:
        raise FileNotFoundError(f"No rolling date-level results found in {RESULTS_DIR}")

    summary = pd.concat(rows, ignore_index=True)
    front_cols = [
        "assumed_treatment_date",
        "att",
        "standard_error",
        "ci_low",
        "ci_high",
        "n_rows",
        "n_treated_stations",
        "n_control_stations",
        "trimmed_rows_if_dropped",
        "trimmed_share_if_dropped",
        "g_model_auc",
        "q_model_rmse",
    ]
    summary = summary.loc[:, front_cols + [col for col in summary.columns if col not in front_cols]]
    summary.to_csv(SUMMARY_OUT, index=False)
    return summary


def main() -> None:
    args = parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    DATE_LEVEL_DIR.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(INPUT_PATH, usecols=USECOLS, parse_dates=["station_hour"], low_memory=False)
    panel = panel[panel["city"].isin(("nyc", "chicago", "boston", "philadelphia", "washington_dc"))].copy()
    for date in args.dates:
        print(f"Running assumed treatment date {date}")
        run_one_date(panel, date)

    rebuild_summary()
    print(f"Wrote {SUMMARY_OUT}")


if __name__ == "__main__":
    main()
