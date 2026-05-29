"""
Run June 20 no-baseline control-group sensitivities.

Window: May 23-June 19, 2025 versus June 20-July 17, 2025. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
continuous-weather differences, pre/post coarse weather-condition indicators,
and categorical hour, day_of_week, and week_index indicators.

This script does not include the baseline-demand covariate. It is the June 20
analog of the October 24 no-baseline control-group sensitivity table.
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
CONTROL_CITIES = ("chicago", "boston", "philadelphia", "washington_dc")
T0_START = "2025-05-23"
T0_END = "2025-06-19 23:00:00"
T1_START = "2025-06-20"
T1_END = "2025-07-17 23:00:00"


def main() -> None:
    one_control_results = []
    for city in CONTROL_CITIES:
        result = run_paired_weighting_analysis(
            base_estimand=f"NYC June 20 ATT versus {city}",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"june_20_nyc_vs_{city}",
            t0_start=T0_START,
            t0_end=T0_END,
            t1_start=T1_START,
            t1_end=T1_END,
            treated_city="nyc",
            control_cities=(city,),
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result["sensitivity"] = "june_20_one_control_city"
        result["control_city"] = city
        one_control_results.append(result)
    one_summary = pd.concat(one_control_results, ignore_index=True)
    one_path = RESULTS_DIR / "june_20_one_control_city_summary.csv"
    one_summary.to_csv(one_path, index=False)
    print(f"Wrote {one_path}")

    leave_one_results = []
    for omitted in CONTROL_CITIES:
        controls = tuple(city for city in CONTROL_CITIES if city != omitted)
        result = run_paired_weighting_analysis(
            base_estimand=f"NYC June 20 ATT excluding {omitted}",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"june_20_leave_one_out_excluding_{omitted}",
            t0_start=T0_START,
            t0_end=T0_END,
            t1_start=T1_START,
            t1_end=T1_END,
            treated_city="nyc",
            control_cities=controls,
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result["sensitivity"] = "june_20_leave_one_control_out"
        result["omitted_control_city"] = omitted
        leave_one_results.append(result)
    leave_one_summary = pd.concat(leave_one_results, ignore_index=True)
    leave_one_path = RESULTS_DIR / "june_20_leave_one_control_out_summary.csv"
    leave_one_summary.to_csv(leave_one_path, index=False)
    print(f"Wrote {leave_one_path}")


if __name__ == "__main__":
    main()
