"""
Run October 24 baseline-demand control-group sensitivities.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: raw ebike_trip_count change at the paired station-hour level.
X covariates: preferred sharp-window weather/time controls plus leave-one-out
pre-treatment station_uid x hour e-bike baseline demand.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT
from baseline_demand_utils import run_baseline_demand_variant


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"
CONTROL_CITIES = ("chicago", "boston", "philadelphia", "washington_dc")
T0_START = "2025-09-26"
T0_END = "2025-10-23 23:00:00"
T1_START = "2025-10-24"
T1_END = "2025-11-20 23:00:00"


def main() -> None:
    one_control_results = []
    for city in CONTROL_CITIES:
        one_control_results.append(
            run_baseline_demand_variant(
                base_estimand=f"NYC sharp-window baseline-demand ATT versus {city}",
                input_path=INPUT_PATH,
                results_dir=RESULTS_DIR,
                output_stem=f"sharp_window_baseline_demand_nyc_vs_{city}",
                t0_start=T0_START,
                t0_end=T0_END,
                t1_start=T1_START,
                t1_end=T1_END,
                treated_city="nyc",
                control_cities=(city,),
                sensitivity="sharp_window_baseline_demand_one_control_city",
                extra_result_cols={"control_city": city},
            )
        )
    one_summary = pd.concat(one_control_results, ignore_index=True)
    one_path = RESULTS_DIR / "sharp_window_baseline_demand_one_control_city_summary.csv"
    one_summary.to_csv(one_path, index=False)
    print(f"Wrote {one_path}")

    leave_one_results = []
    for omitted in CONTROL_CITIES:
        controls = tuple(city for city in CONTROL_CITIES if city != omitted)
        leave_one_results.append(
            run_baseline_demand_variant(
                base_estimand=f"NYC sharp-window baseline-demand ATT excluding {omitted}",
                input_path=INPUT_PATH,
                results_dir=RESULTS_DIR,
                output_stem=f"sharp_window_baseline_demand_leave_one_out_excluding_{omitted}",
                t0_start=T0_START,
                t0_end=T0_END,
                t1_start=T1_START,
                t1_end=T1_END,
                treated_city="nyc",
                control_cities=controls,
                sensitivity="sharp_window_baseline_demand_leave_one_control_out",
                extra_result_cols={"omitted_control_city": omitted},
            )
        )
    leave_one_summary = pd.concat(leave_one_results, ignore_index=True)
    leave_one_path = RESULTS_DIR / "sharp_window_baseline_demand_leave_one_control_out_summary.csv"
    leave_one_summary.to_csv(leave_one_path, index=False)
    print(f"Wrote {leave_one_path}")


if __name__ == "__main__":
    main()
