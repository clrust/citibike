"""
Run June 20 no-baseline control-group sensitivities excluding Chicago.

Chicago is excluded because Divvy station IDs changed around June 1, 2025,
which creates false zero ridership for retained Chicago stations in the May
23-May 30 part of the June 20 panel. This script keeps the June 20 design but
uses only Boston, Philadelphia, and Washington DC as controls.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis  # noqa: E402


RESULTS_DIR = PROJECT_ROOT / "results" / "june_20_no_chicago"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "june_20" / "01_june_20_station_hour_panel_weather.csv"
CONTROL_CITIES = ("boston", "philadelphia", "washington_dc")
T0_START = "2025-05-23"
T0_END = "2025-06-19 23:00:00"
T1_START = "2025-06-20"
T1_END = "2025-07-17 23:00:00"


def run_spec(control_cities: tuple[str, ...], output_stem: str, estimand: str) -> pd.DataFrame:
    return run_paired_weighting_analysis(
        base_estimand=estimand,
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem=output_stem,
        t0_start=T0_START,
        t0_end=T0_END,
        t1_start=T1_START,
        t1_end=T1_END,
        treated_city="nyc",
        control_cities=control_cities,
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )


def main() -> None:
    pooled = run_spec(
        CONTROL_CITIES,
        "june_20_no_chicago_pooled",
        "NYC June 20 ATT excluding Chicago",
    )
    pooled["sensitivity"] = "june_20_no_chicago_pooled"
    pooled_path = RESULTS_DIR / "june_20_no_chicago_pooled_summary.csv"
    pooled.to_csv(pooled_path, index=False)
    print(f"Wrote {pooled_path}")

    one_control_results = []
    for city in CONTROL_CITIES:
        result = run_spec(
            (city,),
            f"june_20_no_chicago_nyc_vs_{city}",
            f"NYC June 20 ATT versus {city}",
        )
        result["sensitivity"] = "june_20_no_chicago_one_control_city"
        result["control_city"] = city
        one_control_results.append(result)
    one_summary = pd.concat(one_control_results, ignore_index=True)
    one_path = RESULTS_DIR / "june_20_no_chicago_one_control_city_summary.csv"
    one_summary.to_csv(one_path, index=False)
    print(f"Wrote {one_path}")

    leave_one_results = []
    for omitted in CONTROL_CITIES:
        controls = tuple(city for city in CONTROL_CITIES if city != omitted)
        result = run_spec(
            controls,
            f"june_20_no_chicago_leave_one_out_excluding_{omitted}",
            f"NYC June 20 ATT excluding Chicago and {omitted}",
        )
        result["sensitivity"] = "june_20_no_chicago_leave_one_control_out"
        result["omitted_control_city"] = omitted
        leave_one_results.append(result)
    leave_one_summary = pd.concat(leave_one_results, ignore_index=True)
    leave_one_path = RESULTS_DIR / "june_20_no_chicago_leave_one_control_out_summary.csv"
    leave_one_summary.to_csv(leave_one_path, index=False)
    print(f"Wrote {leave_one_path}")


if __name__ == "__main__":
    main()
