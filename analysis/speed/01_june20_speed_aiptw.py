"""
Run the June 20 NYC OD-day speed AIPTW analysis.

Window: May 23-June 19, 2025 versus June 20-July 17, 2025. Outcome:
post-minus-pre change in average straight-line speed, measured at the
OD-pair-by-ride-type-by-week_index-by-day_of_week level. Treatment is
electric_bike; control is classic_bike within Citi Bike.

Covariates: paired daily weather differences, pre/post broad weather-condition
indicators, and categorical day_of_week and week_index indicators. Propensity
scores are clipped to [0.01, 0.99]; rows are not dropped by default, but the
output reports how many would be removed under trimming.
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
    city_diagnostics,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
    weather_category,
)


RESULTS_DIR = PROJECT_ROOT / "results" / "speed"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--threshold", type=int, default=50)
    parser.add_argument("--write-predictions", action="store_true")
    return parser.parse_args()


def build_features(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Create the X matrix for the OD-day speed analysis."""

    paired = panel.copy()
    feature_cols: list[str] = []

    # Continuous weather controls follow the paired outcome structure: post
    # condition minus pre condition for the matched day-position.
    for feature_name, base_col in WEATHER_CONTINUOUS.items():
        out_col = f"delta_{feature_name}"
        paired[out_col] = paired[f"{base_col}_t1"] - paired[f"{base_col}_t0"]
        feature_cols.append(out_col)

    # Weather codes are categorical, so use broad pre and post condition
    # indicators rather than subtracting numeric codes.
    paired["condition_t0"] = paired["weather_weather_condition_code_t0"].map(weather_category)
    paired["condition_t1"] = paired["weather_weather_condition_code_t1"].map(weather_category)
    condition_dummies = pd.get_dummies(
        paired[["condition_t0", "condition_t1"]],
        columns=["condition_t0", "condition_t1"],
        prefix=["condition_t0", "condition_t1"],
        dtype="int8",
    )
    paired = pd.concat([paired, condition_dummies], axis=1)
    feature_cols.extend(condition_dummies.columns.to_list())

    # There is no hour dimension in this OD-day speed panel. The time controls
    # therefore match the available paired keys: day of week and week index.
    time_dummies = pd.get_dummies(
        paired[["day_of_week", "week_index"]],
        columns=["day_of_week", "week_index"],
        prefix=["day_of_week", "week_index"],
        dtype="int8",
    )
    paired = pd.concat([paired, time_dummies], axis=1)
    feature_cols.extend(time_dummies.columns.to_list())

    return paired, feature_cols


def main() -> None:
    args = parse_args()
    input_path = PROJECT_ROOT / "data_clean" / "speed" / f"02_june20_speed_paired_panel_threshold{args.threshold}.csv"
    output_stem = f"01_june20_speed_aiptw_threshold{args.threshold}"
    predictions_out = RESULTS_DIR / f"{output_stem}_predictions.csv"
    summary_out = RESULTS_DIR / f"{output_stem}_summary.csv"

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    panel = pd.read_csv(input_path, parse_dates=["date_t0", "date_t1"], low_memory=False)
    if panel.isna().any(axis=1).sum():
        missing_rows = int(panel.isna().any(axis=1).sum())
        raise RuntimeError(f"Speed panel has {missing_rows:,} rows with missing values.")

    paired, feature_cols = build_features(panel)
    config = make_config(
        estimand=f"NYC June 20 OD-day ATT for e-bike average speed, threshold {args.threshold} (row-weighted)",
        station_weighted=False,
        input_path=input_path,
        results_dir=RESULTS_DIR,
        output_stem=output_stem,
        n_folds=5,
        clip_low=0.01,
        clip_high=0.99,
        random_state=20250524,
        t0_start="2025-05-23",
        t0_end="2025-06-19 23:59:59",
        t1_start="2025-06-20",
        t1_end="2025-07-17 23:59:59",
        treated_city="electric_bike",
        control_cities=("classic_bike",),
        outcome_col="avg_speed_mph",
        include_time_controls=True,
        include_daylight_controls=False,
    )

    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    result, estimated = estimate_att(predictions, config)
    diagnostics = city_diagnostics(estimated, config).rename(columns={"city": "ride_type"})

    result["analysis_unit"] = "OD pair x ride type x week_index x day_of_week"
    result["threshold_min_total_rides_per_type"] = args.threshold
    result["speed_filter"] = "duration 1-180 minutes; straight-line distance >=0.05 miles; speed 0.5-30 mph"
    result["treatment"] = "electric_bike"
    result["control"] = "classic_bike"
    result["notes"] = (
        "Unweighted OD-day-cell ATT. Propensity scores are clipped to [0.01, 0.99]; "
        "trimmed_rows_if_dropped reports hypothetical trimming loss."
    )

    result.to_csv(RESULTS_DIR / f"{output_stem}.csv", index=False)
    result.to_csv(summary_out, index=False)
    diagnostics.to_csv(RESULTS_DIR / f"{output_stem}_ride_type_diagnostics.csv", index=False)

    prediction_cols = [
        "station_uid",
        "od_pair",
        "rideable_type",
        "week_index",
        "day_of_week",
        "date_t0",
        "date_t1",
        "A",
        "y0",
        "y1",
        "y_tilde",
        "ride_count_t0",
        "ride_count_t1",
        *feature_cols,
        "condition_t0",
        "condition_t1",
        "g_hat_raw",
        "g_hat",
        "Q0_hat",
        "Q1_hat",
        "aiptw_score",
        "influence_value",
        "analysis_weight",
        "fold",
    ]
    if args.write_predictions:
        estimated.loc[:, prediction_cols].to_csv(predictions_out, index=False)

    print(result.to_string(index=False))
    print(f"Wrote result to {RESULTS_DIR / f'{output_stem}.csv'}")
    print(f"Wrote diagnostics to {RESULTS_DIR / f'{output_stem}_ride_type_diagnostics.csv'}")
    if args.write_predictions:
        print(f"Wrote predictions to {predictions_out}")


if __name__ == "__main__":
    main()
