"""
Run the sharp-window main specification with a log1p e-bike outcome.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: log1p(post ebike_trip_count) - log1p(pre ebike_trip_count) at the
paired station-hour level. This scale addresses the concern that common
proportional shocks can be larger in raw counts for high-demand NYC stations.

X covariates match the preferred sharp-window main specification: paired
continuous-weather differences, pre/post coarse weather-condition indicators,
and categorical hour, day_of_week, and week_index indicators.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
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
OUTPUT_STEM = "sharp_window_log1p_outcome"


def transform_to_log1p_outcome(paired: pd.DataFrame) -> pd.DataFrame:
    """Replace y0/y1/y_tilde with log1p e-bike counts for estimation."""

    out = paired.copy()
    out["raw_y0"] = out["y0"]
    out["raw_y1"] = out["y1"]
    out["y0"] = np.log1p(out["raw_y0"])
    out["y1"] = np.log1p(out["raw_y1"])
    out["y_tilde"] = out["y1"] - out["y0"]
    return out


def main() -> None:
    fit_config = make_config(
        estimand="NYC sharp-window ATT for log1p e-bike trips (row-weighted)",
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
    paired = transform_to_log1p_outcome(paired)
    fit_config = replace(fit_config, outcome_col="log1p_ebike_trip_count")

    predictions = fit_crossfit_nuisance(paired, feature_cols, fit_config)

    results = []
    for station_weighted, suffix, estimand in (
        (False, "row_weighted", "NYC sharp-window ATT for log1p e-bike trips (row-weighted)"),
        (True, "station_weighted", "NYC sharp-window ATT for log1p e-bike trips (station-weighted)"),
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
            outcome_col="log1p_ebike_trip_count",
            include_time_controls=True,
        )
        result, estimated = estimate_att(predictions, config)
        result["sensitivity"] = OUTPUT_STEM
        result["outcome_definition"] = "log1p(y1_ebike_trip_count) - log1p(y0_ebike_trip_count)"
        diagnostics = city_diagnostics(estimated, config)

        config.result_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(config.result_path, index=False)
        diagnostics.to_csv(config.diagnostics_path, index=False)
        results.append(result)
        print(f"Wrote {config.result_path}")
        print(f"Wrote {config.diagnostics_path}")

    summary = pd.concat(results, ignore_index=True)
    summary_path = RESULTS_DIR / f"{OUTPUT_STEM}_summary.csv"
    summary.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()
