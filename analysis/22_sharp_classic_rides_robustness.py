"""
Run the sharp-window station-hour AIPTW sensitivity for classic rides.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: classic_trip_count at the paired station-hour level. X covariates:
paired differences in continuous weather variables, pre/post coarse
weather-condition indicators, and categorical hour, day_of_week, and week_index
indicators. This repeats the preferred sharp-window specification and changes
only the outcome from e-bike trip counts to classic bike trip counts.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC sharp-window ATT for classic rides with weather and time-slot controls",
        input_path=PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv",
        results_dir=RESULTS_DIR,
        output_stem="sharp_classic_rides_robustness",
        t0_start="2025-09-26",
        t0_end="2025-10-23 23:00:00",
        t1_start="2025-10-24",
        t1_end="2025-11-20 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="classic_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "sharp_classic_rides_robustness"
    out = RESULTS_DIR / "sharp_classic_rides_robustness_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
