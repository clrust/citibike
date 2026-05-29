"""
Bootstrap the June 20 NYC OD-day speed threshold sensitivities.

This uses the same OD-day speed design as 01_june20_speed_aiptw.py:
electric_bike is treated, classic_bike is the within-system control, and the
outcome is the post-minus-pre change in straight-line average speed for an
OD-pair-by-ride-type-by-week_index-by-day_of_week cell.

For each threshold, this script fits the cross-fitted nuisance models once and
then resamples OD-pair clusters using fixed nuisance predictions. It does not
refit XGBoost inside bootstrap draws.
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
    WEATHER_CONTINUOUS,
    add_weights,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
    weather_category,
)


RESULTS_DIR = PROJECT_ROOT / "results" / "speed"
DEFAULT_THRESHOLDS = (30, 50, 75, 100)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thresholds", type=int, nargs="+", default=list(DEFAULT_THRESHOLDS))
    parser.add_argument("--n-bootstrap", type=int, default=500)
    parser.add_argument("--random-state", type=int, default=20250524)
    return parser.parse_args()


def build_features(panel: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Create the same X matrix used by the non-bootstrap speed analysis."""

    paired = panel.copy()
    feature_cols: list[str] = []
    for feature_name, base_col in WEATHER_CONTINUOUS.items():
        out_col = f"delta_{feature_name}"
        paired[out_col] = paired[f"{base_col}_t1"] - paired[f"{base_col}_t0"]
        feature_cols.append(out_col)

    paired["condition_t0"] = paired["weather_weather_condition_code_t0"].map(weather_category)
    paired["condition_t1"] = paired["weather_weather_condition_code_t1"].map(weather_category)
    condition_dummies = pd.get_dummies(
        paired[["condition_t0", "condition_t1"]],
        columns=["condition_t0", "condition_t1"],
        prefix=["condition_t0", "condition_t1"],
        dtype="int8",
    )
    paired = pd.concat([paired, condition_dummies], axis=1)
    feature_cols.extend(condition_dummies.columns.to_list())

    time_dummies = pd.get_dummies(
        paired[["day_of_week", "week_index"]],
        columns=["day_of_week", "week_index"],
        prefix=["day_of_week", "week_index"],
        dtype="int8",
    )
    paired = pd.concat([paired, time_dummies], axis=1)
    feature_cols.extend(time_dummies.columns.to_list())
    return paired, feature_cols


def od_pair_components(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse row-level AIPTW components to OD-pair clusters."""

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
            n_rows=("station_uid", "size"),
            n_treated_rows=("A", "sum"),
        )
    )


def bootstrap_att(
    components: pd.DataFrame,
    n_bootstrap: int,
    random_state: int,
) -> tuple[float, float, float, float, np.ndarray]:
    """Resample OD-pair clusters and recompute the normalized ATT estimate."""

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
    return point, se, float(ci_low), float(ci_high), estimates


def run_threshold(threshold: int, n_bootstrap: int, random_state: int) -> tuple[dict[str, object], pd.DataFrame]:
    """Fit one threshold specification and return analytic plus bootstrap output."""

    input_path = PROJECT_ROOT / "data_clean" / "speed" / f"02_june20_speed_paired_panel_threshold{threshold}.csv"
    panel = pd.read_csv(input_path, parse_dates=["date_t0", "date_t1"], low_memory=False)
    if panel.isna().any(axis=1).sum():
        missing_rows = int(panel.isna().any(axis=1).sum())
        raise RuntimeError(f"{input_path} has {missing_rows:,} rows with missing values.")

    paired, feature_cols = build_features(panel)
    config = make_config(
        estimand=f"NYC June 20 OD-day ATT for e-bike average speed, threshold {threshold} (row-weighted)",
        station_weighted=False,
        input_path=input_path,
        results_dir=RESULTS_DIR,
        output_stem=f"02_june20_speed_bootstrap_threshold{threshold}",
        n_folds=5,
        clip_low=0.01,
        clip_high=0.99,
        random_state=random_state,
        t0_start="2025-05-23",
        t0_end="2025-06-19 23:59:59",
        t1_start="2025-06-20",
        t1_end="2025-07-17 23:59:59",
        treated_city="electric_bike",
        control_cities=("classic_bike",),
        outcome_col="avg_speed_mph",
        include_time_controls=True,
        include_daylight_controls=False,
    )

    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    analytic, estimated = estimate_att(predictions, config)
    components = od_pair_components(estimated)
    point, boot_se, boot_ci_low, boot_ci_high, draws = bootstrap_att(
        components,
        n_bootstrap=n_bootstrap,
        random_state=random_state + threshold,
    )

    row = analytic.iloc[0].to_dict()
    row.update(
        {
            "threshold_min_total_rides_per_type": threshold,
            "bootstrap_att": point,
            "bootstrap_standard_error": boot_se,
            "bootstrap_ci_low": boot_ci_low,
            "bootstrap_ci_high": boot_ci_high,
            "n_bootstrap": n_bootstrap,
            "n_od_pair_clusters": len(components),
            "bootstrap_cluster": "station_uid/OD pair",
            "bootstrap_note": (
                "OD-pair cluster bootstrap using fixed cross-fitted nuisance predictions; "
                "XGBoost is not refit inside bootstrap draws."
            ),
        }
    )
    draw_df = pd.DataFrame({"threshold_min_total_rides_per_type": threshold, "draw": np.arange(n_bootstrap), "att": draws})
    return row, draw_df


def main() -> None:
    args = parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    draws: list[pd.DataFrame] = []
    for threshold in args.thresholds:
        print(f"Running threshold {threshold} with {args.n_bootstrap} bootstrap draws")
        row, draw_df = run_threshold(threshold, args.n_bootstrap, args.random_state)
        rows.append(row)
        draws.append(draw_df)

    summary = pd.DataFrame(rows)
    draw_output = pd.concat(draws, ignore_index=True)
    summary_out = RESULTS_DIR / "02_june20_speed_threshold_bootstrap_summary.csv"
    draws_out = RESULTS_DIR / "02_june20_speed_threshold_bootstrap_draws.csv"
    summary.to_csv(summary_out, index=False)
    draw_output.to_csv(draws_out, index=False)
    print(summary[[
        "threshold_min_total_rides_per_type",
        "att",
        "standard_error",
        "ci_low",
        "ci_high",
        "bootstrap_standard_error",
        "bootstrap_ci_low",
        "bootstrap_ci_high",
        "n_rows",
        "n_od_pair_clusters",
        "trimmed_share_if_dropped",
    ]].to_string(index=False))
    print(f"Wrote {summary_out}")
    print(f"Wrote {draws_out}")


if __name__ == "__main__":
    main()
