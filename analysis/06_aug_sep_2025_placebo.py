"""
Run the August-September 2025 pre-treatment placebo.

Window: August 4-24, 2025 versus September 1-21, 2025. Outcome:
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
    # Both windows precede the speed cap, so this weather-only placebo should
    # ideally be close to zero if conditional parallel trends is credible.
    result = run_paired_weighting_analysis(
        base_estimand="NYC placebo ATT, August-September 2025",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "og_placebo_2025_aug_sep"
        / "09_2025_aug_sep_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="placebo_2025_aug_sep",
        t0_start="2025-08-04",
        t0_end="2025-08-24 23:00:00",
        t1_start="2025-09-01",
        t1_end="2025-09-21 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
    )
    result["sensitivity"] = "aug_sep_2025_placebo"
    out = RESULTS_DIR / "aug_sep_2025_placebo_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
