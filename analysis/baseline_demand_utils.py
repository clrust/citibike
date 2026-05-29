"""
Helpers for AIPTW sensitivities with pre-treatment baseline e-bike demand.

The shared baseline covariate is a leave-one-out average of pre-treatment
ebike_trip_count for the same station_uid x hour. It is built after the usual
pre/post station-hour pairing, so it respects each script's date window and
station-retention sample.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aiptw_common import (
    build_paired_dataset,
    city_diagnostics,
    estimate_att,
    fit_crossfit_nuisance,
    make_config,
)


BASELINE_COL = "baseline_station_hour_ebike_pre_loo"


def add_leave_one_out_station_hour_baseline(paired: pd.DataFrame) -> pd.DataFrame:
    """Add station x hour pre-treatment demand, excluding each row's own y0."""

    out = paired.copy()
    group_keys = ["station_uid", "hour"]
    group_sum = out.groupby(group_keys, observed=True)["y0"].transform("sum")
    group_count = out.groupby(group_keys, observed=True)["y0"].transform("size")
    out[BASELINE_COL] = (group_sum - out["y0"]) / (group_count - 1)
    if out[BASELINE_COL].isna().any():
        raise RuntimeError("Baseline demand has missing values; expected at least two rows per station-hour.")
    return out


def run_baseline_demand_variant(
    *,
    base_estimand: str,
    input_path: Path,
    results_dir: Path,
    output_stem: str,
    t0_start: str,
    t0_end: str,
    t1_start: str,
    t1_end: str,
    treated_city: str,
    control_cities: tuple[str, ...],
    sensitivity: str,
    extra_result_cols: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Fit one baseline-demand nuisance model and report row/station targets."""

    fit_config = make_config(
        estimand=f"{base_estimand} (row-weighted)",
        station_weighted=False,
        input_path=input_path,
        results_dir=results_dir,
        output_stem=f"{output_stem}_row_weighted",
        t0_start=t0_start,
        t0_end=t0_end,
        t1_start=t1_start,
        t1_end=t1_end,
        treated_city=treated_city,
        control_cities=control_cities,
        outcome_col="ebike_trip_count",
        include_time_controls=True,
    )

    paired, feature_cols = build_paired_dataset(fit_config)
    paired = add_leave_one_out_station_hour_baseline(paired)
    feature_cols = [*feature_cols, BASELINE_COL]
    predictions = fit_crossfit_nuisance(paired, feature_cols, fit_config)

    results = []
    for station_weighted, suffix, estimand in (
        (False, "row_weighted", f"{base_estimand} (row-weighted)"),
        (True, "station_weighted", f"{base_estimand} (station-weighted)"),
    ):
        config = make_config(
            estimand=estimand,
            station_weighted=station_weighted,
            input_path=input_path,
            results_dir=results_dir,
            output_stem=f"{output_stem}_{suffix}",
            t0_start=t0_start,
            t0_end=t0_end,
            t1_start=t1_start,
            t1_end=t1_end,
            treated_city=treated_city,
            control_cities=control_cities,
            outcome_col="ebike_trip_count",
            include_time_controls=True,
        )
        result, estimated = estimate_att(predictions, config)
        result["sensitivity"] = sensitivity
        result["extra_covariate"] = BASELINE_COL
        if extra_result_cols:
            for key, value in extra_result_cols.items():
                result[key] = value
        diagnostics = city_diagnostics(estimated, config)

        config.result_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(config.result_path, index=False)
        diagnostics.to_csv(config.diagnostics_path, index=False)
        results.append(result)
        print(f"Wrote {config.result_path}")
        print(f"Wrote {config.diagnostics_path}")

    return pd.concat(results, ignore_index=True)
