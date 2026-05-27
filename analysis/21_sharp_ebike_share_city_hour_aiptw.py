"""
Run the sharp-window city-hour e-bike share AIPTW sensitivity.

Window: September 26-October 23, 2025 versus October 24-November 20, 2025.
The outcome is the hourly share of rides that are e-bike rides:

    ebike_share = ebike_trip_count / (ebike_trip_count + classic_trip_count)

The unit is city-hour, paired across the same four-week sharp pre/post windows
as the preferred main station-hour specification. NYC city-hours are treated;
Chicago, Boston, Philadelphia, and Washington DC city-hours are controls. X
covariates are paired differences in continuous weather variables, pre/post
coarse weather-condition indicators, and categorical hour, day_of_week, and
week_index indicators.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, mean_squared_error, roc_auc_score

from aiptw_common import PROJECT_ROOT, weather_category


INPUT_PATH = PROJECT_ROOT / "data_clean" / "sensitivities" / "13_sharp_ebike_share_city_hour.csv"
RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
SUMMARY_OUT = RESULTS_DIR / "sharp_ebike_share_city_hour_aiptw_summary.csv"
PREDICTIONS_OUT = RESULTS_DIR / "sharp_ebike_share_city_hour_aiptw_predictions.csv"
CITY_DIAGNOSTICS_OUT = RESULTS_DIR / "sharp_ebike_share_city_hour_aiptw_city_diagnostics.csv"
PROPENSITY_OUT = RESULTS_DIR / "sharp_ebike_share_city_hour_aiptw_propensity_diagnostics.csv"
T0_START = pd.Timestamp("2025-09-26")
T0_END = pd.Timestamp("2025-10-23 23:00:00")
T1_START = pd.Timestamp("2025-10-24")
T1_END = pd.Timestamp("2025-11-20 23:00:00")
CONTROLS = ("chicago", "boston", "philadelphia", "washington_dc")
CLIP_LOW = 0.01
CLIP_HIGH = 0.99
RANDOM_STATE = 20250524

WEATHER_CONTINUOUS = {
    "temp_c": "weather_temp_c",
    "precip_mm": "weather_precip_mm",
    "snow_mm": "weather_snow_mm",
    "relative_humidity": "weather_relative_humidity",
    "wind_speed_kph": "weather_wind_speed_kph",
}


def import_xgboost():
    try:
        from xgboost import XGBClassifier, XGBRegressor
    except ImportError as exc:
        raise SystemExit(
            "xgboost is required for this analysis. Install it in this environment with "
            "`python3 -m pip install xgboost` and rerun."
        ) from exc
    return XGBClassifier, XGBRegressor


def build_paired_city_hour_dataset() -> tuple[pd.DataFrame, list[str]]:
    """Create paired city-hour e-bike-share changes and AIPTW feature columns."""

    usecols = [
        "period",
        "city",
        "station_hour",
        "week_index",
        "day_of_week",
        "hour",
        "ebike_trip_count",
        "classic_trip_count",
        "total_trip_count",
        "ebike_share",
        "weather_temp_c",
        "weather_precip_mm",
        "weather_snow_mm",
        "weather_relative_humidity",
        "weather_wind_speed_kph",
        "weather_weather_condition_code",
    ]
    city_hour = pd.read_csv(INPUT_PATH, usecols=usecols, parse_dates=["station_hour"], low_memory=False)
    city_hour = city_hour[city_hour["city"].isin(("nyc", *CONTROLS))].copy()
    city_hour["weather_snow_mm"] = city_hour["weather_snow_mm"].fillna(0)

    keys = ["city", "week_index", "day_of_week", "hour"]
    weather_cols = list(WEATHER_CONTINUOUS.values()) + ["weather_weather_condition_code"]

    t0 = city_hour[city_hour["period"] == "pre"].copy()
    t1 = city_hour[city_hour["period"] == "post"].copy()
    t0 = t0.loc[:, keys + ["station_hour", "ebike_share", "ebike_trip_count", "classic_trip_count", "total_trip_count", *weather_cols]]
    t1 = t1.loc[:, keys + ["station_hour", "ebike_share", "ebike_trip_count", "classic_trip_count", "total_trip_count", *weather_cols]]
    t0 = t0.rename(
        columns={
            "station_hour": "station_hour_t0",
            "ebike_share": "y0",
            "ebike_trip_count": "ebike_trips_t0",
            "classic_trip_count": "classic_trips_t0",
            "total_trip_count": "total_trips_t0",
        }
    )
    t1 = t1.rename(
        columns={
            "station_hour": "station_hour_t1",
            "ebike_share": "y1",
            "ebike_trip_count": "ebike_trips_t1",
            "classic_trip_count": "classic_trips_t1",
            "total_trip_count": "total_trips_t1",
        }
    )
    paired = t0.merge(t1, on=keys, how="inner", suffixes=("_t0", "_t1"), validate="one_to_one")
    paired["A"] = (paired["city"] == "nyc").astype("int8")
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
    time_dummies = pd.get_dummies(
        paired[["hour", "day_of_week", "week_index"]],
        columns=["hour", "day_of_week", "week_index"],
        prefix=["hour", "day_of_week", "week_index"],
        dtype="int8",
    )
    paired = pd.concat([paired, condition_dummies, time_dummies], axis=1)
    feature_cols.extend(condition_dummies.columns.to_list())
    feature_cols.extend(time_dummies.columns.to_list())
    return paired.sort_values(["city", "week_index", "day_of_week", "hour"]).reset_index(drop=True), feature_cols


def make_time_slot_folds(df: pd.DataFrame, n_folds: int = 5) -> np.ndarray:
    """Assign cross-fitting folds by paired time slot.

    City-level folds are not viable here because there is only one treated city.
    Instead, each fold holds out all cities for a subset of matched
    week/day/hour slots, so every training fold contains NYC and all control
    cities while still predicting held-out city-hours.
    """

    slots = df[["week_index", "day_of_week", "hour"]].drop_duplicates().sort_values(
        ["week_index", "day_of_week", "hour"]
    )
    slots["fold"] = np.arange(len(slots), dtype=np.int16) % n_folds
    return df.merge(slots, on=["week_index", "day_of_week", "hour"], how="left")["fold"].to_numpy(dtype=np.int16)


def fit_nuisance(df: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame:
    """Fit conservative cross-fitted XGBoost nuisance models for city-hours."""

    XGBClassifier, XGBRegressor = import_xgboost()
    out = df.copy()
    out["fold"] = make_time_slot_folds(out)
    out["g_hat_raw"] = np.nan
    out["Q0_hat"] = np.nan
    out["Q1_hat"] = np.nan

    X_g_all = out.loc[:, feature_cols]
    X_q_all = pd.concat([out[["A"]], X_g_all], axis=1)
    y_a = out["A"].to_numpy()
    y = out["y_tilde"].to_numpy()

    for fold in sorted(out["fold"].unique()):
        train = out["fold"].to_numpy() != fold
        test = ~train
        if len(np.unique(y_a[train])) < 2:
            raise RuntimeError(f"Fold {fold} training set has only one treatment class.")

        g = XGBClassifier(
            objective="binary:logistic",
            eval_metric="logloss",
            n_estimators=120,
            max_depth=2,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_lambda=5.0,
            tree_method="hist",
            n_jobs=-1,
            random_state=RANDOM_STATE + int(fold),
        )
        q = XGBRegressor(
            objective="reg:squarederror",
            n_estimators=160,
            max_depth=2,
            learning_rate=0.04,
            subsample=0.8,
            colsample_bytree=0.8,
            min_child_weight=5,
            reg_lambda=5.0,
            tree_method="hist",
            n_jobs=-1,
            random_state=RANDOM_STATE + 100 + int(fold),
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

    out["g_hat"] = out["g_hat_raw"].clip(CLIP_LOW, CLIP_HIGH)
    return out


def estimate_att(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Estimate the NYC city-hour ATT using the standard AIPTW ATT score."""

    out = predictions.copy()
    a = out["A"].to_numpy(dtype=float)
    y = out["y_tilde"].to_numpy(dtype=float)
    q0 = out["Q0_hat"].to_numpy(dtype=float)
    g = out["g_hat"].to_numpy(dtype=float)
    h = a - (1.0 - a) * g / (1.0 - g)
    att = float(np.sum(h * (y - q0)) / np.sum(a))

    influence = (h * (y - q0) - att * a) / np.mean(a)
    se = float(np.std(influence, ddof=1) / np.sqrt(len(out)))
    out["aiptw_score"] = h * (y - q0) / np.sum(a)
    out["influence_value"] = influence

    raw_g = out["g_hat_raw"]
    outside = (raw_g < CLIP_LOW) | (raw_g > CLIP_HIGH)
    result = pd.DataFrame(
        [
            {
                "estimand": "Sharp-window AIPTW ATT for NYC city-hour e-bike share",
                "outcome": "city-hour ebike_trip_count / (ebike_trip_count + classic_trip_count)",
                "unit": "paired city-hour",
                "t0_start": str(T0_START),
                "t0_end": str(T0_END),
                "t1_start": str(T1_START),
                "t1_end": str(T1_END),
                "att": att,
                "standard_error": se,
                "ci_low": float(att - 1.96 * se),
                "ci_high": float(att + 1.96 * se),
                "n_rows": len(out),
                "n_treated_rows": int(out["A"].sum()),
                "n_control_rows": int((1 - out["A"]).sum()),
                "n_treated_cities": int(out.loc[out["A"] == 1, "city"].nunique()),
                "n_control_cities": int(out.loc[out["A"] == 0, "city"].nunique()),
                "clip_low": CLIP_LOW,
                "clip_high": CLIP_HIGH,
                "g_hat_mean": float(out["g_hat"].mean()),
                "g_hat_min": float(out["g_hat"].min()),
                "g_hat_max": float(out["g_hat"].max()),
                "g_hat_treated_mean": float(out.loc[out["A"] == 1, "g_hat"].mean()),
                "g_hat_control_mean": float(out.loc[out["A"] == 0, "g_hat"].mean()),
                "n_g_hat_below_0_01": int((raw_g < CLIP_LOW).sum()),
                "n_g_hat_above_0_99": int((raw_g > CLIP_HIGH).sum()),
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


def propensity_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """Report propensity-score quantiles by treatment group."""

    rows = []
    for treatment_value, label in ((1, "nyc"), (0, "controls"), (None, "all")):
        subset = df if treatment_value is None else df[df["A"] == treatment_value]
        quantiles = subset["g_hat_raw"].quantile([0, 0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1])
        row = {"group": label, "n_rows": len(subset)}
        row.update({f"g_hat_raw_q{int(q * 100):02d}": float(value) for q, value in quantiles.items()})
        rows.append(row)
    return pd.DataFrame(rows)


def city_diagnostics(df: pd.DataFrame) -> pd.DataFrame:
    """Summarize paired outcomes, shares, and propensity scores by city."""

    return (
        df.groupby("city", as_index=False)
        .agg(
            n_rows=("city", "size"),
            mean_y0=("y0", "mean"),
            mean_y1=("y1", "mean"),
            mean_y_tilde=("y_tilde", "mean"),
            total_ebike_t0=("ebike_trips_t0", "sum"),
            total_classic_t0=("classic_trips_t0", "sum"),
            total_ebike_t1=("ebike_trips_t1", "sum"),
            total_classic_t1=("classic_trips_t1", "sum"),
            mean_g_hat_raw=("g_hat_raw", "mean"),
            min_g_hat_raw=("g_hat_raw", "min"),
            max_g_hat_raw=("g_hat_raw", "max"),
        )
        .sort_values("city")
    )


def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    paired, feature_cols = build_paired_city_hour_dataset()
    missing = paired[feature_cols].isna().sum()
    if missing.any():
        raise RuntimeError(f"Missing AIPTW features:\n{missing[missing > 0]}")

    predictions = fit_nuisance(paired, feature_cols)
    result, predictions = estimate_att(predictions)
    diagnostics = city_diagnostics(predictions)
    propensities = propensity_diagnostics(predictions)

    result.to_csv(SUMMARY_OUT, index=False)
    predictions.to_csv(PREDICTIONS_OUT, index=False)
    diagnostics.to_csv(CITY_DIAGNOSTICS_OUT, index=False)
    propensities.to_csv(PROPENSITY_OUT, index=False)
    print(f"Wrote {SUMMARY_OUT}")
    print(f"Wrote {PREDICTIONS_OUT}")
    print(f"Wrote {CITY_DIAGNOSTICS_OUT}")
    print(f"Wrote {PROPENSITY_OUT}")


if __name__ == "__main__":
    main()
