"""
Run the September-November 2024 placebo with time-slot controls in X.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC placebo ATT, September-November 2024 with time controls",
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "2024_sep_nov_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="placebo_2024_sep_nov_time_controls",
        t0_start="2024-09-02",
        t0_end="2024-09-22 23:00:00",
        t1_start="2024-11-04",
        t1_end="2024-11-24 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "sep_nov_2024_placebo_time_controls"
    out = RESULTS_DIR / "sep_nov_2024_placebo_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
