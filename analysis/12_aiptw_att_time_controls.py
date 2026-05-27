"""
Run the original September-November AIPTW spec with time-slot controls in X.

Window: September 1-21, 2025 versus November 3-23, 2025. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
differences in continuous weather variables, pre/post coarse weather-condition
indicators, and categorical hour, day_of_week, and week_index indicators.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = (
    PROJECT_ROOT
    / "data_clean"
    / "og_main_spec_sept_nov"
    / "07_station_hour_panel_weather.csv"
)


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC ATT with weather and time-slot controls",
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem="main_time_controls",
        t0_start="2025-09-01",
        t0_end="2025-09-21 23:00:00",
        t1_start="2025-11-03",
        t1_end="2025-11-23 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "main_time_controls"
    out = RESULTS_DIR / "main_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
