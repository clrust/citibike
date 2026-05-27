"""
Run original September-November NYC-vs-one-control-city sensitivities.

Window: September 1-21, 2025 versus November 3-23, 2025. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
differences in continuous weather variables plus pre/post coarse
weather-condition indicators. Each run compares NYC to one control city.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = (
    PROJECT_ROOT
    / "data_clean"
    / "og_main_spec_sept_nov"
    / "07_station_hour_panel_weather.csv"
)


def main() -> None:
    # Keep the original Sept-Nov window, e-bike outcome, and weather-only X
    # fixed while changing the control group to one city at a time.
    results = []
    for control in CONTROLS:
        result = run_paired_weighting_analysis(
            base_estimand=f"NYC ATT versus {control}",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"nyc_vs_{control}",
            t0_start="2025-09-01",
            t0_end="2025-09-21 23:00:00",
            t1_start="2025-11-03",
            t1_end="2025-11-23 23:00:00",
            treated_city="nyc",
            control_cities=(control,),
            outcome_col="ebike_trip_count",
        )
        result["sensitivity"] = "one_control_city"
        result["control_city"] = control
        results.append(result)
    out = RESULTS_DIR / "one_control_city_summary.csv"
    pd.concat(results, ignore_index=True).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
