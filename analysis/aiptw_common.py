from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_squared_error, roc_auc_score


PROJECT_ROOT = Path(__file__).resolve().parents[1]
T0_START = pd.Timestamp("2025-09-01")
T0_END = pd.Timestamp("2025-09-21 23:00:00")
T1_START = pd.Timestamp("2025-11-03")
T1_END = pd.Timestamp("2025-11-23 23:00:00")
WEATHER_CONTINUOUS = {
    "temp_c": "weather_temp_c",
    "precip_mm": "weather_precip_mm",
    "snow_mm": "weather_snow_mm",
    "relative_humidity": "weather_relative_humidity",
    "wind_speed_kph": "weather_wind_speed_kph",
}


@dataclass(frozen=True)
class AiptwConfig:
    estimand: str
    station_weighted: bool
    input_path: Path
    result_path: Path
    prediction_path: Path
    diagnostics_path: Path
    n_folds: int
    clip_low: float
    clip_high: float
    random_state: int
    t0_start: pd.Timestamp
    t0_end: pd.Timestamp
    t1_start: pd.Timestamp
    t1_end: pd.Timestamp
    treated_city: str
    control_cities: tuple[str, ...] | None
    outcome_col: str


def make_config(
    *,
    estimand: str,
    station_weighted: bool,
    input_path: Path,
    results_dir: Path,
    output_stem: str,
    n_folds: int = 5,
    clip_low: float = 0.01,
    clip_high: float = 0.99,
    random_state: int = 20250524,
    t0_start: str = "2025-09-01",
    t0_end: str = "2025-09-21 23:00:00",
    t1_start: str = "2025-11-03",
    t1_end: str = "2025-11-23 23:00:00",
    treated_city: str = "nyc",
    control_cities: tuple[str, ...] | None = None,
    outcome_col: str = "ebike_trip_count",
) -> AiptwConfig:
    return AiptwConfig(
        estimand=estimand,
        station_weighted=station_weighted,
        input_path=input_path,
        result_path=results_dir / f"{output_stem}.csv",
        prediction_path=results_dir / f"{output_stem}_predictions.csv",
        diagnostics_path=results_dir / f"{output_stem}_city_diagnostics.csv",
        n_folds=n_folds,
        clip_low=clip_low,
        clip_high=clip_high,
        random_state=random_state,
        t0_start=pd.Timestamp(t0_start),
        t0_end=pd.Timestamp(t0_end),
        t1_start=pd.Timestamp(t1_start),
        t1_end=pd.Timestamp(t1_end),
        treated_city=treated_city,
        control_cities=control_cities,
        outcome_col=outcome_col,
    )


def parse_args(description: str, estimand: str, station_weighted: bool) -> AiptwConfig:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--input", type=Path, default=PROJECT_ROOT / "data_clean" / "07_station_hour_panel_weather.csv")
    parser.add_argument("--results-dir", type=Path, default=PROJECT_ROOT / "results")
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--clip-low", type=float, default=0.01)
    parser.add_argument("--clip-high", type=float, default=0.99)
    parser.add_argument("--random-state", type=int, default=20250524)
    parser.add_argument("--t0-start", default=str(T0_START.date()))
    parser.add_argument("--t0-end", default=str(T0_END))
    parser.add_argument("--t1-start", default=str(T1_START.date()))
    parser.add_argument("--t1-end", default=str(T1_END))
    parser.add_argument("--treated-city", default="nyc")
    parser.add_argument("--control-cities", nargs="+")
    parser.add_argument("--outcome-col", default="ebike_trip_count")
    args = parser.parse_args()

    stem = "02_aiptw_att_station_weighted" if station_weighted else "01_aiptw_att_row_weighted"
    return make_config(
        estimand=estimand,
        station_weighted=station_weighted,
        input_path=args.input,
        results_dir=args.results_dir,
        output_stem=stem,
        n_folds=args.n_folds,
        clip_low=args.clip_low,
        clip_high=args.clip_high,
        random_state=args.random_state,
        t0_start=args.t0_start,
        t0_end=args.t0_end,
        t1_start=args.t1_start,
        t1_end=args.t1_end,
        treated_city=args.treated_city,
        control_cities=tuple(args.control_cities) if args.control_cities else None,
        outcome_col=args.outcome_col,
    )


def first_three_week_window(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    out = df[(df["station_hour"] >= start) & (df["station_hour"] <= end)].copy()
    out["week_index"] = ((out["station_hour"].dt.normalize() - start).dt.days // 7 + 1).astype("int8")
    out["day_of_week"] = out["station_hour"].dt.dayofweek.astype("int8")
    out["hour"] = out["station_hour"].dt.hour.astype("int8")
    return out


def weather_category(code: object) -> str:
    if pd.isna(code):
        return "unknown"
    try:
        value = int(code)
    except (TypeError, ValueError):
        return "unknown"
    if value in {1, 2}:
        return "clear_or_fair"
    if value in {3, 4}:
        return "cloudy"
    if value in {5, 6}:
        return "fog"
    if value in {7, 8, 9, 17, 18}:
        return "rain"
    if value in {10, 11}:
        return "freezing_rain"
    if value in {12, 13, 19, 20}:
        return "sleet"
    if value in {14, 15, 16, 21, 22}:
        return "snow"
    if value in {23, 24, 25, 26, 27}:
        return "thunderstorm_or_storm"
    return "unknown"


def build_paired_dataset(config: AiptwConfig) -> tuple[pd.DataFrame, list[str]]:
    usecols = [
        "station_uid",
        "city",
        "system",
        "station_hour",
        config.outcome_col,
        "weather_temp_c",
        "weather_precip_mm",
        "weather_snow_mm",
        "weather_relative_humidity",
        "weather_wind_speed_kph",
        "weather_weather_condition_code",
    ]
    panel = pd.read_csv(config.input_path, usecols=usecols, parse_dates=["station_hour"], low_memory=False)
    keep_cities = {config.treated_city}
    if config.control_cities is None:
        keep_cities.update(city for city in panel["city"].dropna().unique() if city != config.treated_city)
    else:
        keep_cities.update(config.control_cities)
    panel = panel[panel["city"].isin(keep_cities)].copy()
    panel["weather_snow_mm"] = panel["weather_snow_mm"].fillna(0)

    keys = ["station_uid", "week_index", "day_of_week", "hour"]
    meta_cols = ["station_uid", "city", "system", "week_index", "day_of_week", "hour"]
    weather_cols = list(WEATHER_CONTINUOUS.values()) + ["weather_weather_condition_code"]

    t0 = first_three_week_window(panel, config.t0_start, config.t0_end)
    t1 = first_three_week_window(panel, config.t1_start, config.t1_end)
    t0 = t0.loc[:, meta_cols + [config.outcome_col, "station_hour"] + weather_cols].rename(
        columns={config.outcome_col: "y0", "station_hour": "station_hour_t0"}
    )
    t1 = t1.loc[:, keys + [config.outcome_col, "station_hour"] + weather_cols].rename(
        columns={config.outcome_col: "y1", "station_hour": "station_hour_t1"}
    )

    paired = t0.merge(t1, on=keys, how="inner", suffixes=("_t0", "_t1"), validate="one_to_one")
    paired["A"] = (paired["city"] == config.treated_city).astype("int8")
    paired["y_tilde"] = paired["y1"] - paired["y0"]

    feature_cols: list[str] = []
    for feature_name, col in WEATHER_CONTINUOUS.items():
        out_col = f"delta_{feature_name}"
        paired[out_col] = paired[f"{col}_t1"] - paired[f"{col}_t0"]
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

    paired = paired.sort_values(["city", "station_uid", "week_index", "day_of_week", "hour"]).reset_index(drop=True)
    return paired, feature_cols


def make_station_stratified_folds(df: pd.DataFrame, n_folds: int, random_state: int) -> np.ndarray:
    stations = df[["station_uid", "A"]].drop_duplicates().reset_index(drop=True)
    rng = np.random.default_rng(random_state)
    station_to_fold: dict[str, int] = {}
    for treatment_value in (0, 1):
        station_ids = stations.loc[stations["A"] == treatment_value, "station_uid"].to_numpy(copy=True)
        rng.shuffle(station_ids)
        for idx, station_uid in enumerate(station_ids):
            station_to_fold[str(station_uid)] = idx % n_folds
    return df["station_uid"].astype(str).map(station_to_fold).astype("int16").to_numpy()


def import_xgboost():
    try:
        from xgboost import XGBClassifier, XGBRegressor
    except ImportError as exc:
        raise SystemExit(
            "xgboost is required for this analysis. Install it in this environment with "
            "`python3 -m pip install xgboost` and rerun."
        ) from exc
    return XGBClassifier, XGBRegressor


def fit_crossfit_nuisance(df: pd.DataFrame, feature_cols: list[str], config: AiptwConfig) -> pd.DataFrame:
    XGBClassifier, XGBRegressor = import_xgboost()
    out = df.copy()
    out["fold"] = make_station_stratified_folds(out, config.n_folds, config.random_state)
    out["g_hat_raw"] = np.nan
    out["Q0_hat"] = np.nan
    out["Q1_hat"] = np.nan

    X_g_all = out.loc[:, feature_cols]
    X_q_all = pd.concat([out[["A"]], X_g_all], axis=1)
    y_a = out["A"].to_numpy()
    y = out["y_tilde"].to_numpy()

    for fold in range(config.n_folds):
        train = out["fold"].to_numpy() != fold
        test = ~train

        g = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=300,
            max_depth=3,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=10,
            reg_lambda=1.0,
            tree_method="hist",
            n_jobs=-1,
            random_state=config.random_state + fold,
        )
        q = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=400,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=10,
            reg_lambda=1.0,
            tree_method="hist",
            n_jobs=-1,
            random_state=config.random_state + 100 + fold,
        )

        g.fit(X_g_all.loc[train], y_a[train])
        q.fit(X_q_all.loc[train], y[train])
        out.loc[test, "g_hat_raw"] = g.predict_proba(X_g_all.loc[test])[:, 1]

        X_q_test_0 = X_q_all.loc[test].copy()
        X_q_test_0["A"] = 0
        X_q_test_1 = X_q_all.loc[test].copy()
        X_q_test_1["A"] = 1
        out.loc[test, "Q0_hat"] = q.predict(X_q_test_0)
        out.loc[test, "Q1_hat"] = q.predict(X_q_test_1)

    out["g_hat"] = out["g_hat_raw"].clip(config.clip_low, config.clip_high)
    return out


def add_weights(df: pd.DataFrame, station_weighted: bool) -> pd.DataFrame:
    out = df.copy()
    if station_weighted:
        station_counts = out.groupby("station_uid")["station_uid"].transform("size")
        out["analysis_weight"] = 1.0 / station_counts
    else:
        out["analysis_weight"] = 1.0
    return out


def estimate_att(df: pd.DataFrame, config: AiptwConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = add_weights(df, config.station_weighted)
    a = out["A"].to_numpy(dtype=float)
    y = out["y_tilde"].to_numpy(dtype=float)
    q0 = out["Q0_hat"].to_numpy(dtype=float)
    g = out["g_hat"].to_numpy(dtype=float)
    w = out["analysis_weight"].to_numpy(dtype=float)

    h = a - (1.0 - a) * g / (1.0 - g)
    numerator = np.sum(w * h * (y - q0))
    denominator = np.sum(w * a)
    att = numerator / denominator

    denominator_bar = np.mean(w * a)
    influence = (w * h * (y - q0) - att * w * a) / denominator_bar
    se = float(np.std(influence, ddof=1) / np.sqrt(len(out)))
    ci_low = float(att - 1.96 * se)
    ci_high = float(att + 1.96 * se)

    out["aiptw_score"] = w * h * (y - q0) / denominator
    out["influence_value"] = influence

    raw_g = out["g_hat_raw"]
    outside = (raw_g < config.clip_low) | (raw_g > config.clip_high)
    result = pd.DataFrame(
        [
            {
                "estimand": config.estimand,
                "outcome_col": config.outcome_col,
                "treated_city": config.treated_city,
                "control_cities": ",".join(config.control_cities) if config.control_cities else "all_except_treated",
                "t0_start": str(config.t0_start),
                "t0_end": str(config.t0_end),
                "t1_start": str(config.t1_start),
                "t1_end": str(config.t1_end),
                "att": float(att),
                "standard_error": se,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "n_rows": len(out),
                "n_treated_rows": int(out["A"].sum()),
                "n_control_rows": int((1 - out["A"]).sum()),
                "n_treated_stations": int(out.loc[out["A"] == 1, "station_uid"].nunique()),
                "n_control_stations": int(out.loc[out["A"] == 0, "station_uid"].nunique()),
                "n_folds": config.n_folds,
                "g_hat_mean": float(out["g_hat"].mean()),
                "g_hat_min": float(out["g_hat"].min()),
                "g_hat_max": float(out["g_hat"].max()),
                "g_hat_treated_mean": float(out.loc[out["A"] == 1, "g_hat"].mean()),
                "g_hat_control_mean": float(out.loc[out["A"] == 0, "g_hat"].mean()),
                "n_g_hat_below_0_01": int((raw_g < config.clip_low).sum()),
                "n_g_hat_above_0_99": int((raw_g > config.clip_high).sum()),
                "share_g_hat_outside_0_01_0_99": float(outside.mean()),
                "n_treated_g_hat_outside": int(outside[out["A"] == 1].sum()),
                "n_control_g_hat_outside": int(outside[out["A"] == 0].sum()),
                "share_treated_g_hat_outside": float(outside[out["A"] == 1].mean()),
                "share_control_g_hat_outside": float(outside[out["A"] == 0].mean()),
                "trimmed_rows_if_dropped": int(outside.sum()),
                "trimmed_share_if_dropped": float(outside.mean()),
                "g_model_auc": float(roc_auc_score(out["A"], out["g_hat_raw"])),
                "g_model_log_loss": float(log_loss(out["A"], out["g_hat_raw"])),
                "q_model_rmse": float(mean_squared_error(out["y_tilde"], out["Q1_hat"].where(out["A"] == 1, out["Q0_hat"])) ** 0.5),
            }
        ]
    )
    return result, out


def city_diagnostics(df: pd.DataFrame, config: AiptwConfig) -> pd.DataFrame:
    raw_g = df["g_hat_raw"]
    outside = (raw_g < config.clip_low) | (raw_g > config.clip_high)
    tmp = df.assign(g_hat_outside=outside)
    return (
        tmp.groupby("city", as_index=False)
        .agg(
            n_rows=("city", "size"),
            n_stations=("station_uid", "nunique"),
            mean_y0=("y0", "mean"),
            mean_y1=("y1", "mean"),
            mean_y_tilde=("y_tilde", "mean"),
            mean_g_hat=("g_hat", "mean"),
            share_g_hat_clipped=("g_hat_outside", "mean"),
        )
        .sort_values("city")
    )


def run_analysis(config: AiptwConfig) -> None:
    paired, feature_cols = build_paired_dataset(config)
    predictions = fit_crossfit_nuisance(paired, feature_cols, config)
    result, predictions = estimate_att(predictions, config)
    diagnostics = city_diagnostics(predictions, config)

    config.result_path.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(config.result_path, index=False)
    diagnostics.to_csv(config.diagnostics_path, index=False)

    prediction_cols = [
        "station_uid",
        "city",
        "system",
        "week_index",
        "day_of_week",
        "hour",
        "station_hour_t0",
        "station_hour_t1",
        "A",
        "y0",
        "y1",
        "y_tilde",
        *feature_cols,
        "condition_t0",
        "condition_t1",
        "g_hat_raw",
        "g_hat",
        "Q0_hat",
        "Q1_hat",
        "aiptw_score",
        "influence_value",
        "analysis_weight",
        "fold",
    ]
    predictions.loc[:, prediction_cols].to_csv(config.prediction_path, index=False)
    print(f"Wrote result to {config.result_path}")
    print(f"Wrote predictions to {config.prediction_path}")
    print(f"Wrote diagnostics to {config.diagnostics_path}")


def run_paired_weighting_analysis(
    *,
    base_estimand: str,
    input_path: Path,
    results_dir: Path,
    output_stem: str,
    t0_start: str,
    t0_end: str,
    t1_start: str,
    t1_end: str,
    treated_city: str = "nyc",
    control_cities: tuple[str, ...] | None = None,
    outcome_col: str = "ebike_trip_count",
    n_folds: int = 5,
    clip_low: float = 0.01,
    clip_high: float = 0.99,
    random_state: int = 20250524,
    write_predictions: bool = False,
) -> pd.DataFrame:
    fit_config = make_config(
        estimand=f"{base_estimand} (row-weighted)",
        station_weighted=False,
        input_path=input_path,
        results_dir=results_dir,
        output_stem=f"{output_stem}_row_weighted",
        n_folds=n_folds,
        clip_low=clip_low,
        clip_high=clip_high,
        random_state=random_state,
        t0_start=t0_start,
        t0_end=t0_end,
        t1_start=t1_start,
        t1_end=t1_end,
        treated_city=treated_city,
        control_cities=control_cities,
        outcome_col=outcome_col,
    )
    paired, feature_cols = build_paired_dataset(fit_config)
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
            n_folds=n_folds,
            clip_low=clip_low,
            clip_high=clip_high,
            random_state=random_state,
            t0_start=t0_start,
            t0_end=t0_end,
            t1_start=t1_start,
            t1_end=t1_end,
            treated_city=treated_city,
            control_cities=control_cities,
            outcome_col=outcome_col,
        )
        result, estimated = estimate_att(predictions, config)
        diagnostics = city_diagnostics(estimated, config)
        config.result_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(config.result_path, index=False)
        diagnostics.to_csv(config.diagnostics_path, index=False)
        if write_predictions:
            prediction_cols = [
                "station_uid",
                "city",
                "system",
                "week_index",
                "day_of_week",
                "hour",
                "station_hour_t0",
                "station_hour_t1",
                "A",
                "y0",
                "y1",
                "y_tilde",
                *feature_cols,
                "condition_t0",
                "condition_t1",
                "g_hat_raw",
                "g_hat",
                "Q0_hat",
                "Q1_hat",
                "aiptw_score",
                "influence_value",
                "analysis_weight",
                "fold",
            ]
            estimated.loc[:, prediction_cols].to_csv(config.prediction_path, index=False)
        results.append(result)
        print(f"Wrote {suffix} result to {config.result_path}")
        print(f"Wrote {suffix} diagnostics to {config.diagnostics_path}")
    return pd.concat(results, ignore_index=True)
