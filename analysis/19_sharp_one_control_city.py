"""
Run sharp-window NYC-vs-one-control-city AIPTW ATT sensitivities.

These repeat the preferred four-week October 2025 specification, changing only
the control group to one city at a time. The date windows, outcome, weather
controls, and time-slot controls are otherwise identical to the preferred sharp
specification.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "sensitivities" / "sharp_window_station_hour_panel_weather.csv"


def main() -> None:
    results = []
    for control in CONTROLS:
        result = run_paired_weighting_analysis(
            base_estimand=f"NYC sharp-window ATT versus {control}",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"sharp_nyc_vs_{control}",
            t0_start="2025-09-26",
            t0_end="2025-10-23 23:00:00",
            t1_start="2025-10-24",
            t1_end="2025-11-20 23:00:00",
            treated_city="nyc",
            control_cities=(control,),
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result["sensitivity"] = "sharp_one_control_city"
        result["control_city"] = control
        results.append(result)
    out = RESULTS_DIR / "sharp_one_control_city_summary.csv"
    pd.concat(results, ignore_index=True).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
