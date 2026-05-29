"""
Bootstrap the June 20 baseline-demand e-bike ATT excluding Chicago.

Controls are Boston, Philadelphia, and Washington DC. Chicago is excluded
because the June 2025 Divvy station ID change creates false zero ridership in
the early June 20 pre-window panel.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


ANALYSIS_ROOT = Path(__file__).resolve().parents[1]
if str(ANALYSIS_ROOT) not in sys.path:
    sys.path.insert(0, str(ANALYSIS_ROOT))

from aiptw_common import (  # noqa: E402
    PROJECT_ROOT,
    add_weights,
    build_paired_dataset,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
)
from baseline_demand_utils import BASELINE_COL, add_leave_one_out_station_hour_baseline  # noqa: E402


RESULTS_DIR = PROJECT_ROOT / "results" / "june_20_no_chicago"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "june_20" / "01_june_20_station_hour_panel_weather.csv"
CONTROL_CITIES = ("boston", "philadelphia", "washington_dc")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=20250524)
    return parser.parse_args()


def station_components(df: pd.DataFrame) -> pd.DataFrame:
    work = add_weights(df, station_weighted=False)
    a = work["A"].to_numpy(dtype=float)
    g = work["g_hat"].to_numpy(dtype=float)
    y = work["y_tilde"].to_numpy(dtype=float)
    q0 = work["Q0_hat"].to_numpy(dtype=float)
    w = work["analysis_weight"].to_numpy(dtype=float)
    h = a - (1.0 - a) * g / (1.0 - g)
    work["numerator_component"] = w * h * (y - q0)
    work["denominator_component"] = w * a
    return (
        work.groupby("station_uid", as_index=False)
        .agg(
            numerator=("numerator_component", "sum"),
            denominator=("denominator_component", "sum"),
            A=("A", "first"),
            city=("city", "first"),
        )
    )


def bootstrap_att(components: pd.DataFrame, n_bootstrap: int, random_state: int) -> tuple[float, float, float, float]:
    rng = np.random.default_rng(random_state)
    numerator = components["numerator"].to_numpy(dtype=float)
    denominator = components["denominator"].to_numpy(dtype=float)
    point = float(numerator.sum() / denominator.sum())
    estimates = np.empty(n_bootstrap)
    n_clusters = len(components)
    for draw in range(n_bootstrap):
        idx = rng.integers(0, n_clusters, size=n_clusters)
        estimates[draw] = numerator[idx].sum() / denominator[idx].sum()
    se = float(estimates.std(ddof=1))
    ci_low, ci_high = np.quantile(estimates, [0.025, 0.975])
    return point, se, float(ci_low), float(ci_high)


def main() -> None:
    args = parse_args()
    config = make_config(
        estimand="NYC June 20 ATT excluding Chicago with station-hour baseline demand controls",
        station_weighted=False,
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem="june_20_baseline_demand_no_chicago_bootstrap",
        random_state=args.random_state,
        t0_start="2025-05-23",
        t0_end="2025-06-19 23:00:00",
        t1_start="2025-06-20",
        t1_end="2025-07-17 23:00:00",
        treated_city="nyc",
        control_cities=CONTROL_CITIES,
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )

    paired, feature_cols = build_paired_dataset(config)
    paired = add_leave_one_out_station_hour_baseline(paired)
    feature_cols = [*feature_cols, BASELINE_COL]
    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    analytic, estimated = estimate_att(predictions, config)
    components = station_components(estimated)
    point, boot_se, boot_ci_low, boot_ci_high = bootstrap_att(
        components,
        args.n_bootstrap,
        args.random_state,
    )

    row = analytic.iloc[0].to_dict()
    row.update(
        {
            "target": "row_weighted",
            "extra_covariate": BASELINE_COL,
            "bootstrap_att": point,
            "bootstrap_standard_error": boot_se,
            "bootstrap_ci_low": boot_ci_low,
            "bootstrap_ci_high": boot_ci_high,
            "n_bootstrap": args.n_bootstrap,
            "n_station_clusters": len(components),
            "excluded_control_city": "chicago",
            "bootstrap_note": "Station-level bootstrap using fixed cross-fitted nuisance predictions.",
        }
    )

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "june_20_baseline_demand_no_chicago_bootstrap_summary.csv"
    pd.DataFrame([row]).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
