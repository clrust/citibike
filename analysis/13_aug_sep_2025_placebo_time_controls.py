"""
Run the August-September 2025 placebo with time-slot controls in X.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC placebo ATT, August-September 2025 with time controls",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "2025_aug_sep_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="placebo_2025_aug_sep_time_controls",
        t0_start="2025-08-04",
        t0_end="2025-08-24 23:00:00",
        t1_start="2025-09-01",
        t1_end="2025-09-21 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "aug_sep_2025_placebo_time_controls"
    out = RESULTS_DIR / "aug_sep_2025_placebo_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
