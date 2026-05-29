"""
Run the October 24 sharp-window main specification with propensity trimming.

This is identical to the preferred main sharp-window AIPTW specification except
that observations with raw propensity scores outside [0.01, 0.99] are dropped
instead of retained with clipped propensity scores. Only the row-weighted ATT
is reported because trimming can remove different numbers of paired
station-hours from different stations.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import (
    PROJECT_ROOT,
    city_diagnostics,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
    build_paired_dataset,
)


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"


def main() -> None:
    config = make_config(
        estimand="NYC sharp-window ATT with propensity trimming",
        station_weighted=False,
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem="sharp_window_trimmed",
        t0_start="2025-09-26",
        t0_end="2025-10-23 23:00:00",
        t1_start="2025-10-24",
        t1_end="2025-11-20 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )

    paired, feature_cols = build_paired_dataset(config)
    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    outside = (predictions["g_hat_raw"] < config.clip_low) | (predictions["g_hat_raw"] > config.clip_high)
    trimmed = predictions.loc[~outside].copy()

    result, estimated = estimate_att(trimmed, config)
    diagnostics = city_diagnostics(estimated, config)

    result["trim_rule"] = "drop rows with raw g_hat outside [0.01, 0.99]"
    result["rows_before_trim"] = len(predictions)
    result["rows_after_trim"] = len(trimmed)
    result["rows_dropped_by_trim"] = int(outside.sum())
    result["share_dropped_by_trim"] = float(outside.mean())
    result["treated_rows_dropped_by_trim"] = int(outside[predictions["A"] == 1].sum())
    result["control_rows_dropped_by_trim"] = int(outside[predictions["A"] == 0].sum())
    result["treated_share_dropped_by_trim"] = float(outside[predictions["A"] == 1].mean())
    result["control_share_dropped_by_trim"] = float(outside[predictions["A"] == 0].mean())
    result["stations_before_trim"] = int(predictions["station_uid"].nunique())
    result["stations_after_trim"] = int(trimmed["station_uid"].nunique())
    result["treated_stations_before_trim"] = int(predictions.loc[predictions["A"] == 1, "station_uid"].nunique())
    result["treated_stations_after_trim"] = int(trimmed.loc[trimmed["A"] == 1, "station_uid"].nunique())
    result["control_stations_before_trim"] = int(predictions.loc[predictions["A"] == 0, "station_uid"].nunique())
    result["control_stations_after_trim"] = int(trimmed.loc[trimmed["A"] == 0, "station_uid"].nunique())

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_path = RESULTS_DIR / "sharp_window_trimmed_summary.csv"
    diagnostics_path = RESULTS_DIR / "sharp_window_trimmed_city_diagnostics.csv"
    result.to_csv(result_path, index=False)
    diagnostics.to_csv(diagnostics_path, index=False)
    print(f"Wrote {result_path}")
    print(f"Wrote {diagnostics_path}")


if __name__ == "__main__":
    main()
