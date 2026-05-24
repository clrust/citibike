"""
Run control-city placebo treatment sensitivities.
"""

from __future__ import annotations

import pandas as pd

from aiptw_common import PROJECT_ROOT, run_paired_weighting_analysis


CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def main() -> None:
    # Pretend each control city was treated and compare it to the other control
    # cities. Large placebo effects here would weaken confidence that the main
    # NYC estimate is isolating the speed-cap change rather than general shocks.
    results = []
    for treated in CONTROLS:
        placebo_controls = tuple(city for city in CONTROLS if city != treated)
        result = run_paired_weighting_analysis(
            base_estimand=f"Placebo ATT treating {treated} as treated",
            input_path=PROJECT_ROOT / "data_clean" / "07_station_hour_panel_weather.csv",
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
