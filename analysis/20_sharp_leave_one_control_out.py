"""
Run sharp-window leave-one-control-city-out AIPTW ATT sensitivities.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: ebike_trip_count at the paired station-hour level. X covariates:
paired differences in continuous weather variables, pre/post coarse
weather-condition indicators, and categorical hour, day_of_week, and week_index
indicators. Each run omits one city from the pooled controls.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"


def main() -> None:
    results = []
    for omitted in CONTROLS:
        controls = tuple(city for city in CONTROLS if city != omitted)
        result = run_paired_weighting_analysis(
            base_estimand=f"NYC sharp-window ATT excluding {omitted}",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"sharp_leave_one_out_excluding_{omitted}",
            t0_start="2025-09-26",
            t0_end="2025-10-23 23:00:00",
            t1_start="2025-10-24",
            t1_end="2025-11-20 23:00:00",
            treated_city="nyc",
            control_cities=controls,
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result["sensitivity"] = "sharp_leave_one_control_out"
        result["omitted_control_city"] = omitted
        results.append(result)
    out = RESULTS_DIR / "sharp_leave_one_control_out_summary.csv"
    pd.concat(results, ignore_index=True).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
