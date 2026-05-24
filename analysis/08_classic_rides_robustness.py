"""
Run the main paired AIPTW design with classic ride counts as the outcome.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    # Same design as the main specification, but replace e-bike ride counts with
    # classic ride counts. This checks whether the estimated change is specific
    # to the mode affected by the speed cap.
    result = run_paired_weighting_analysis(
        base_estimand="NYC ATT for classic rides",
        input_path=PROJECT_ROOT / "data_clean" / "07_station_hour_panel_weather.csv",
        results_dir=RESULTS_DIR,
        output_stem="classic_rides_main_window",
        t0_start="2025-09-01",
        t0_end="2025-09-21 23:00:00",
        t1_start="2025-11-03",
        t1_end="2025-11-23 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="classic_trip_count",
    )
    result["sensitivity"] = "classic_rides_robustness"
    out = RESULTS_DIR / "classic_rides_robustness_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
