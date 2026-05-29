"""
Run the sharp-window main specification with baseline e-bike demand in X.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: raw ebike_trip_count change at the paired station-hour level.
Additional covariate: leave-one-out pre-treatment average e-bike trips for
the same station_uid x hour. The leave-one-out construction avoids placing the
exact paired y0 observation into its own covariate.

Other X covariates match the preferred sharp-window main specification:
paired continuous-weather differences, pre/post coarse weather-condition
indicators, and categorical hour, day_of_week, and week_index indicators.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import (
    PROJECT_ROOT,
    build_paired_dataset,
    city_diagnostics,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
)


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"
OUTPUT_STEM = "sharp_window_baseline_demand_controls"


def add_leave_one_out_station_hour_baseline(paired: pd.DataFrame) -> pd.DataFrame:
    """Add pre-treatment station x hour demand, excluding each row's own y0."""

    out = paired.copy()
    group_keys = ["station_uid", "hour"]
    group_sum = out.groupby(group_keys, observed=True)["y0"].transform("sum")
    group_count = out.groupby(group_keys, observed=True)["y0"].transform("size")
    out["baseline_station_hour_ebike_pre_loo"] = (group_sum - out["y0"]) / (group_count - 1)
    if out["baseline_station_hour_ebike_pre_loo"].isna().any():
        raise RuntimeError("Baseline demand has missing values; expected at least two pre-period rows per station-hour.")
    return out


def main() -> None:
    fit_config = make_config(
        estimand="NYC sharp-window ATT with station-hour baseline demand controls (row-weighted)",
        station_weighted=False,
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem=f"{OUTPUT_STEM}_row_weighted",
        t0_start="2025-09-26",
        t0_end="2025-10-23 23:00:00",
        t1_start="2025-10-24",
        t1_end="2025-11-20 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )

    paired, feature_cols = build_paired_dataset(fit_config)
    paired = add_leave_one_out_station_hour_baseline(paired)
    feature_cols = [*feature_cols, "baseline_station_hour_ebike_pre_loo"]

    baseline = paired["baseline_station_hour_ebike_pre_loo"]
    baseline_diagnostics = pd.DataFrame(
        [
            {
                "baseline_definition": "leave-one-out pre-treatment mean ebike_trip_count by station_uid x hour",
                "n_rows": len(paired),
                "n_groups": int(paired.groupby(["station_uid", "hour"], observed=True).ngroups),
                "mean": float(baseline.mean()),
                "std": float(baseline.std()),
                "min": float(baseline.min()),
                "p25": float(baseline.quantile(0.25)),
                "median": float(baseline.quantile(0.50)),
                "p75": float(baseline.quantile(0.75)),
                "p90": float(baseline.quantile(0.90)),
                "p95": float(baseline.quantile(0.95)),
                "p99": float(baseline.quantile(0.99)),
                "max": float(baseline.max()),
                "share_zero": float((baseline == 0).mean()),
            }
        ]
    )

    predictions = fit_crossfit_nuisance(paired, feature_cols, fit_config)

    results = []
    for station_weighted, suffix, estimand in (
        (False, "row_weighted", "NYC sharp-window ATT with station-hour baseline demand controls (row-weighted)"),
        (True, "station_weighted", "NYC sharp-window ATT with station-hour baseline demand controls (station-weighted)"),
    ):
        config = make_config(
            estimand=estimand,
            station_weighted=station_weighted,
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"{OUTPUT_STEM}_{suffix}",
            t0_start="2025-09-26",
            t0_end="2025-10-23 23:00:00",
            t1_start="2025-10-24",
            t1_end="2025-11-20 23:00:00",
            treated_city="nyc",
            control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result, estimated = estimate_att(predictions, config)
        result["sensitivity"] = OUTPUT_STEM
        result["extra_covariate"] = "baseline_station_hour_ebike_pre_loo"
        diagnostics = city_diagnostics(estimated, config)

        config.result_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(config.result_path, index=False)
        diagnostics.to_csv(config.diagnostics_path, index=False)
        results.append(result)
        print(f"Wrote {config.result_path}")
        print(f"Wrote {config.diagnostics_path}")

    summary = pd.concat(results, ignore_index=True)
    summary_path = RESULTS_DIR / f"{OUTPUT_STEM}_summary.csv"
    diagnostics_path = RESULTS_DIR / f"{OUTPUT_STEM}_baseline_diagnostics.csv"
    summary.to_csv(summary_path, index=False)
    baseline_diagnostics.to_csv(diagnostics_path, index=False)
    print(f"Wrote {summary_path}")
    print(f"Wrote {diagnostics_path}")


if __name__ == "__main__":
    main()
