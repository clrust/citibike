"""
Bootstrap the August-September 2025 placebo ATT.

This reruns the placebo nuisance models once, then resamples station_uid
clusters using the fixed cross-fitted nuisance predictions. It does not refit
XGBoost inside each bootstrap draw.
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


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=20250524)
    return parser.parse_args()


def station_components(df: pd.DataFrame, station_weighted: bool) -> pd.DataFrame:
    """Collapse row-level AIPTW components to station clusters."""

    work = add_weights(df, station_weighted)
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
    fit_config = make_config(
        estimand="NYC placebo ATT, August-September 2025 (row-weighted)",
        station_weighted=False,
        input_path=PROJECT_ROOT
        / "data_clean"
        / "sensitivities"
        / "2025_aug_sep_station_hour_panel_weather_filled50.csv",
        results_dir=RESULTS_DIR,
        output_stem="placebo_2025_aug_sep_bootstrap",
        random_state=args.random_state,
        t0_start="2025-08-04",
        t0_end="2025-08-24 23:00:00",
        t1_start="2025-09-01",
        t1_end="2025-09-21 23:00:00",
        treated_city="nyc",
        control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
        outcome_col="ebike_trip_count",
    )
    paired, feature_cols = build_paired_dataset(fit_config)
    predictions = fit_crossfit_nuisance(paired, feature_cols, fit_config)

    rows = []
    for station_weighted, target in ((False, "row_weighted"), (True, "station_weighted")):
        config = make_config(
            estimand=f"NYC placebo ATT, August-September 2025 ({target})",
            station_weighted=station_weighted,
            input_path=fit_config.input_path,
            results_dir=RESULTS_DIR,
            output_stem=f"placebo_2025_aug_sep_bootstrap_{target}",
            random_state=args.random_state,
            t0_start="2025-08-04",
            t0_end="2025-08-24 23:00:00",
            t1_start="2025-09-01",
            t1_end="2025-09-21 23:00:00",
            treated_city="nyc",
            control_cities=("chicago", "boston", "philadelphia", "washington_dc"),
            outcome_col="ebike_trip_count",
        )
        analytic, estimated = estimate_att(predictions, config)
        components = station_components(estimated, station_weighted)
        point, boot_se, boot_ci_low, boot_ci_high = bootstrap_att(components, args.n_bootstrap, args.random_state)
        row = analytic.iloc[0].to_dict()
        row.update(
            {
                "target": target,
                "bootstrap_att": point,
                "bootstrap_standard_error": boot_se,
                "bootstrap_ci_low": boot_ci_low,
                "bootstrap_ci_high": boot_ci_high,
                "n_bootstrap": args.n_bootstrap,
                "n_station_clusters": len(components),
                "bootstrap_note": "Station-level bootstrap using fixed cross-fitted nuisance predictions.",
            }
        )
        rows.append(row)

    out = RESULTS_DIR / "aug_sep_2025_placebo_bootstrap_summary.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
