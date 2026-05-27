"""
Run original September-November control-city placebo sensitivities.

Window: September 1-21, 2025 versus November 3-23, 2025. Outcome:
ebike_trip_count at the paired station-hour level. X covariates: paired
differences in continuous weather variables plus pre/post coarse
weather-condition indicators. Each run pretends one control city is treated and
uses the remaining control cities as controls.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
INPUT_PATH = (
    PROJECT_ROOT
    / "data_clean"
    / "og_main_spec_sept_nov"
    / "07_station_hour_panel_weather.csv"
)


def main() -> None:
    # Pretend each control city was treated while holding the Sept-Nov window,
    # e-bike outcome, and weather-only X fixed.
    results = []
    for treated in CONTROLS:
        placebo_controls = tuple(city for city in CONTROLS if city != treated)
        result = run_paired_weighting_analysis(
            base_estimand=f"Placebo ATT treating {treated} as treated",
            input_path=INPUT_PATH,
            results_dir=RESULTS_DIR,
            output_stem=f"placebo_treated_{treated}",
            t0_start="2025-09-01",
            t0_end="2025-09-21 23:00:00",
            t1_start="2025-11-03",
            t1_end="2025-11-23 23:00:00",
            treated_city=treated,
            control_cities=placebo_controls,
            outcome_col="ebike_trip_count",
        )
        result["sensitivity"] = "control_city_placebo"
        result["placebo_treated_city"] = treated
        results.append(result)
    out = RESULTS_DIR / "control_city_placebos_summary.csv"
    pd.concat(results, ignore_index=True).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
