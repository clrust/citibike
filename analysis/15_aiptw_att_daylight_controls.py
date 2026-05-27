"""
Run the original September-November AIPTW spec with delta daylight in X.

This is retained as a sensitivity now that the sharp October window is the
preferred main specification. It adds the paired change in daylight status
between t0 and t1.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC ATT with weather and daylight controls",
        input_path=PROJECT_ROOT / "data_clean" / "07_station_hour_panel_weather.csv",
        results_dir=RESULTS_DIR,
        output_stem="main_daylight_controls",
        t0_start="2025-09-01",
        t0_end="2025-09-21 23:00:00",
        t1_start="2025-11-03",
        t1_end="2025-11-23 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_daylight_controls=True,
    )
    result["sensitivity"] = "main_daylight_controls"
    out = RESULTS_DIR / "main_daylight_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
