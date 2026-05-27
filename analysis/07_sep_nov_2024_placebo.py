"""
Run the September-November 2024 prior-year placebo.

Window: September 2-22, 2024 versus November 4-24, 2024. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
differences in continuous weather variables plus pre/post coarse
weather-condition indicators. No time-slot controls are included in this
weather-only placebo.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    # Repeat the original seasonal comparison one year earlier to probe whether
    # NYC diverges from controls over the same calendar windows absent treatment.
    result = run_paired_weighting_analysis(
        base_estimand="NYC placebo ATT, September-November 2024",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "og_placebo_2024_sep_nov"
        / "09_2024_sep_nov_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="placebo_2024_sep_nov",
        t0_start="2024-09-02",
        t0_end="2024-09-22 23:00:00",
        t1_start="2024-11-04",
        t1_end="2024-11-24 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
    )
    result["sensitivity"] = "sep_nov_2024_placebo"
    out = RESULTS_DIR / "sep_nov_2024_placebo_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
