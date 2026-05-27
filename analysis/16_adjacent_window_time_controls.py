"""
Run the adjacent-window e-bike trips sensitivity with time-slot controls.

Window: September 29-October 19, 2025 versus October 27-November 16, 2025,
skipping the treatment week. Outcome: ebike_trip_count at the paired
station-hour level. X covariates: paired differences in continuous weather
variables, pre/post coarse weather-condition indicators, and categorical hour,
day_of_week, and week_index indicators.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC adjacent-window ATT with weather and time-slot controls",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "10_adjacent_window_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="adjacent_window_time_controls",
        t0_start="2025-09-29",
        t0_end="2025-10-19 23:00:00",
        t1_start="2025-10-27",
        t1_end="2025-11-16 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "adjacent_window_time_controls"
    out = RESULTS_DIR / "adjacent_window_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
