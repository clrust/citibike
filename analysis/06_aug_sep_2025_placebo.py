"""
Run the August-September 2025 pre-treatment placebo.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    # Pre-treatment placebo: compare August to September 2025 using the same
    # NYC-vs-controls design. Because both windows are before the speed cap,
    # this should ideally be close to zero if conditional parallel trends holds.
    result = run_paired_weighting_analysis(
        base_estimand="NYC placebo ATT, August-September 2025",
        input_path=PROJECT_ROOT / "data_clean" / "sensitivities" / "2025_aug_sep_station_hour_panel_weather_filled50.csv",
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
