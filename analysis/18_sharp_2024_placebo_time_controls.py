"""
Run the 2024 sharp-window placebo with time controls.

Window: September 26-October 23, 2024 versus October 24-November 20, 2024.
Outcome: ebike_trip_count at the paired station-hour level. X covariates:
paired differences in continuous weather variables, pre/post coarse
weather-condition indicators, and categorical hour, day_of_week, and week_index
indicators. There was no NYC October 24, 2024 speed-cap event, so this is a
same-calendar placebo check.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC 2024 sharp-window placebo ATT with weather and time-slot controls",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "12_sharp_2024_placebo_station_hour_panel_weather.csv",
        results_dir=RESULTS_DIR,
        output_stem="sharp_2024_placebo_time_controls",
        t0_start="2024-09-26",
        t0_end="2024-10-23 23:00:00",
        t1_start="2024-10-24",
        t1_end="2024-11-20 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "sharp_2024_placebo_time_controls"
    out = RESULTS_DIR / "sharp_2024_placebo_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
