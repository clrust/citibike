"""
Compute station-level bootstrap confidence intervals for the main specification.

This uses the saved cross-fitted nuisance predictions from the main e-bike
specification and resamples station_uid clusters. It does not refit XGBoost in
each bootstrap replicate.
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from aiptw_common import PROJECT_ROOT


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", default=PROJECT_ROOT / "results" / "01_aiptw_att_row_weighted_predictions.csv")
    parser.add_argument("--out", default=PROJECT_ROOT / "results" / "sensitivities" / "main_spec_bootstrap_ci.csv")
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=20250524)
    return parser.parse_args()


def station_components(df: pd.DataFrame, station_weighted: bool) -> pd.DataFrame:
    work = df.copy()
    if station_weighted:
        work["analysis_weight"] = 1.0 / work.groupby("station_uid")["station_uid"].transform("size")
    else:
        work["analysis_weight"] = 1.0
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
    point = numerator.sum() / denominator.sum()
    n = len(components)
    estimates = np.empty(n_bootstrap)
    for draw in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        estimates[draw] = numerator[idx].sum() / denominator[idx].sum()
    se = float(estimates.std(ddof=1))
    ci_low, ci_high = np.quantile(estimates, [0.025, 0.975])
    return float(point), se, float(ci_low), float(ci_high)


def main() -> None:
    args = parse_args()
    df = pd.read_csv(args.predictions, low_memory=False)
    rows = []
    for station_weighted, target in (
        (False, "row_weighted"),
        (True, "station_weighted"),
    ):
        components = station_components(df, station_weighted)
        point, se, ci_low, ci_high = bootstrap_att(components, args.n_bootstrap, args.random_state)
        rows.append(
            {
                "target": target,
                "att": point,
                "bootstrap_standard_error": se,
                "bootstrap_ci_low": ci_low,
                "bootstrap_ci_high": ci_high,
                "n_bootstrap": args.n_bootstrap,
                "n_station_clusters": len(components),
                "note": "Station-level bootstrap using fixed cross-fitted nuisance predictions.",
            }
        )
    out = pd.io.common.stringify_path(args.out)
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
