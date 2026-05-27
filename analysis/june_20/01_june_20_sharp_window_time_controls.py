"""
Run the June 20, 2025 sharp-window station-hour e-bike specification.

Window: May 23-June 19, 2025 versus June 20-July 17, 2025, treating the Citi
Bike operational speed reduction as active at midnight on June 20. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
differences in continuous weather variables, pre/post coarse weather-condition
indicators, and categorical hour, day_of_week, and week_index indicators.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis  # noqa: E402


RESULTS_DIR = PROJECT_ROOT / "results" / "june_20"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "june_20" / "01_june_20_station_hour_panel_weather.csv"


def main() -> None:
    result = run_paired_weighting_analysis(
        base_estimand="NYC June 20 sharp-window ATT with weather and time-slot controls",
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem="june_20_sharp_window_time_controls",
        t0_start="2025-05-23",
        t0_end="2025-06-19 23:00:00",
        t1_start="2025-06-20",
        t1_end="2025-07-17 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )
    result["sensitivity"] = "june_20_sharp_window_time_controls"
    out = RESULTS_DIR / "june_20_sharp_window_time_controls_summary.csv"
    result.to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
