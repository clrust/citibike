"""
Bootstrap the October 24 sharp-window baseline-demand AIPTW ATT.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
Outcome: raw ebike_trip_count change at the paired station-hour level.
X covariates: preferred sharp-window weather/time controls plus leave-one-out
pre-treatment station_uid x hour e-bike baseline demand.

This fits the cross-fitted nuisance models once, then resamples station_uid
clusters using fixed nuisance predictions. It does not refit XGBoost inside
each bootstrap draw.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from aiptw_common import (
    PROJECT_ROOT,
    add_weights,
    build_paired_dataset,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
)
from baseline_demand_utils import BASELINE_COL, add_leave_one_out_station_hour_baseline


RESULTS_DIR = PROJECT_ROOT / "results" / "main_spec"
INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=20250524)
    return parser.parse_args()


def station_components(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse row-level AIPTW numerator and denominator to stations."""

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
    """Resample station clusters and recompute the normalized ATT estimate."""

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
        estimand="NYC sharp-window ATT with station-hour baseline demand controls",
        station_weighted=False,
        input_path=INPUT_PATH,
        results_dir=RESULTS_DIR,
        output_stem="sharp_window_baseline_demand_bootstrap",
        random_state=args.random_state,
        t0_start="2025-09-26",
        t0_end="2025-10-23 23:00:00",
        t1_start="2025-10-24",
        t1_end="2025-11-20 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
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
            "bootstrap_note": (
                "Station-level bootstrap using fixed cross-fitted nuisance predictions. "
                "Station-weighted ATT is identical by construction for this balanced station panel."
            ),
        }
    )

    out = RESULTS_DIR / "sharp_window_baseline_demand_bootstrap_summary.csv"
    pd.DataFrame([row]).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
