"""
Diagnose Citi Bike origin-destination coverage for the June 20 speed design.

This script does not estimate treatment effects. It reads the May-July 2025
Citi Bike trip files, keeps rides in the four-week pre/post June 20 windows,
and summarizes whether station-level origin-destination pairs are dense enough
for an OD-pair-by-day speed panel.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data_raw" / "citi_bike"
OUT_DIR = PROJECT_ROOT / "data_clean" / "speed"
SUMMARY_OUT = OUT_DIR / "01_june20_od_pair_diagnostics_summary.csv"
DAILY_DIST_OUT = OUT_DIR / "01_june20_od_pair_daily_ride_count_distribution.csv"
PAIR_DIST_OUT = OUT_DIR / "01_june20_od_pair_coverage_distribution.csv"
PAIRED_THRESHOLDS_OUT = OUT_DIR / "01_june20_od_pair_paired_thresholds.csv"

RAW_FILES = (
    RAW_DIR / "202505-citibike-tripdata.zip",
    RAW_DIR / "202506-citibike-tripdata.zip",
    RAW_DIR / "202507-citibike-tripdata.zip",
)
PRE_START = pd.Timestamp("2025-05-23")
PRE_END = pd.Timestamp("2025-06-19 23:59:59.999999")
POST_START = pd.Timestamp("2025-06-20")
POST_END = pd.Timestamp("2025-07-17 23:59:59.999999")
WINDOW_DATES = pd.date_range(PRE_START.normalize(), POST_END.normalize(), freq="D")
N_DAYS = len(WINDOW_DATES)

USECOLS = [
    "ride_id",
    "rideable_type",
    "started_at",
    "ended_at",
    "start_station_id",
    "end_station_id",
    "start_lat",
    "start_lng",
    "end_lat",
    "end_lng",
]


def read_filtered_trips() -> pd.DataFrame:
    """Read raw Citi Bike zips and keep trips in the June 20 analysis window."""

    chunks: list[pd.DataFrame] = []
    for path in RAW_FILES:
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith(".csv") or member.lower().startswith("jc-"):
                    continue
                with archive.open(member) as handle:
                    for chunk in pd.read_csv(handle, usecols=USECOLS, chunksize=500_000, low_memory=False):
                        chunk["started_at"] = pd.to_datetime(chunk["started_at"], errors="coerce")
                        keep = chunk["started_at"].between(PRE_START, POST_END)
                        keep &= chunk["rideable_type"].isin(["electric_bike", "classic_bike"])
                        keep &= chunk["start_station_id"].notna() & chunk["end_station_id"].notna()
                        keep &= chunk["start_lat"].notna() & chunk["start_lng"].notna()
                        keep &= chunk["end_lat"].notna() & chunk["end_lng"].notna()
                        if keep.any():
                            chunks.append(chunk.loc[keep, USECOLS].copy())
    if not chunks:
        raise RuntimeError("No June 20 window Citi Bike trips found.")
    trips = pd.concat(chunks, ignore_index=True)
    trips["ended_at"] = pd.to_datetime(trips["ended_at"], errors="coerce")
    trips = trips.dropna(subset=["started_at", "ended_at"])
    trips["date"] = trips["started_at"].dt.normalize()
    trips["period"] = np.where(trips["started_at"] < POST_START, "pre", "post")
    trips["od_pair"] = trips["start_station_id"].astype("string") + " -> " + trips["end_station_id"].astype("string")
    return trips


def summarize_daily_counts(trips: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Summarize rides per OD-pair-day by ride type and coverage rule."""

    daily = (
        trips.groupby(["rideable_type", "od_pair", "date"], as_index=False)
        .agg(rides=("ride_id", "count"))
        .sort_values(["rideable_type", "od_pair", "date"])
    )

    pair = (
        daily.groupby(["rideable_type", "od_pair"], as_index=False)
        .agg(
            observed_days=("date", "nunique"),
            total_rides=("rides", "sum"),
            mean_rides_on_observed_days=("rides", "mean"),
            median_rides_on_observed_days=("rides", "median"),
            max_rides_on_observed_days=("rides", "max"),
            pre_days=("date", lambda s: int((s < POST_START).sum())),
            post_days=("date", lambda s: int((s >= POST_START).sum())),
        )
    )
    pair["appears_pre_and_post"] = (pair["pre_days"] > 0) & (pair["post_days"] > 0)
    pair["appears_every_day"] = pair["observed_days"].eq(N_DAYS)

    both_types = (
        pair[pair["appears_pre_and_post"]]
        .pivot(index="od_pair", columns="rideable_type", values="observed_days")
        .dropna()
        .reset_index()
    )
    both_types["has_both_ride_types_pre_post"] = True

    quantiles = [0, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95, 0.99, 1.0]
    daily_dist = (
        daily.groupby("rideable_type")["rides"]
        .quantile(quantiles)
        .rename("rides_per_observed_od_day")
        .reset_index()
        .rename(columns={"level_1": "quantile"})
    )
    pair_dist = (
        pair.groupby("rideable_type")[["observed_days", "total_rides", "mean_rides_on_observed_days"]]
        .quantile(quantiles)
        .reset_index()
        .rename(columns={"level_1": "quantile"})
    )
    return daily, pair, pd.concat([daily_dist.assign(distribution="daily"), pair_dist.assign(distribution="pair")])


def add_pairing_keys(trips: pd.DataFrame) -> pd.DataFrame:
    """Attach within-window week/day keys for pre/post pairing."""

    out = trips.copy()
    pre_mask = out["started_at"] < POST_START
    out["window_start"] = np.where(pre_mask, PRE_START, POST_START)
    out["window_start"] = pd.to_datetime(out["window_start"])
    out["days_since_window_start"] = (out["date"] - out["window_start"]).dt.days
    out["week_index"] = out["days_since_window_start"] // 7
    out["day_of_week"] = out["date"].dt.dayofweek
    return out


def paired_threshold_diagnostics(trips: pd.DataFrame) -> pd.DataFrame:
    """Report actual pre/post paired rows under candidate retention thresholds."""

    keyed = add_pairing_keys(trips)
    daily = (
        keyed.groupby(["od_pair", "rideable_type", "period", "week_index", "day_of_week"], as_index=False)
        .agg(rides=("ride_id", "count"))
    )

    totals = (
        daily.groupby(["od_pair", "rideable_type"], as_index=False)
        .agg(total_rides=("rides", "sum"), observed_period_days=("rides", "size"))
    )
    total_wide = totals.pivot(index="od_pair", columns="rideable_type", values="total_rides")
    period_wide = daily.pivot_table(
        index="od_pair",
        columns=["rideable_type", "period"],
        values="rides",
        aggfunc="sum",
        fill_value=0,
    )
    for col in [
        ("classic_bike", "pre"),
        ("classic_bike", "post"),
        ("electric_bike", "pre"),
        ("electric_bike", "post"),
    ]:
        if col not in period_wide.columns:
            period_wide[col] = 0
    eligible_both_periods = period_wide[
        (period_wide[("classic_bike", "pre")] > 0)
        & (period_wide[("classic_bike", "post")] > 0)
        & (period_wide[("electric_bike", "pre")] > 0)
        & (period_wide[("electric_bike", "post")] > 0)
    ].index.astype(str)

    pre = daily[daily["period"] == "pre"].rename(columns={"rides": "rides_pre"})
    post = daily[daily["period"] == "post"].rename(columns={"rides": "rides_post"})
    paired = pre.merge(
        post,
        on=["od_pair", "rideable_type", "week_index", "day_of_week"],
        how="inner",
        validate="one_to_one",
    )

    thresholds = [1, 5, 10, 20, 30, 40, 50, 75, 100, 150, 200]
    rows = []
    for threshold in thresholds:
        eligible_totals = total_wide.loc[total_wide.index.astype(str).isin(set(eligible_both_periods))]
        keep_pairs = eligible_totals[
            (eligible_totals["classic_bike"] >= threshold) & (eligible_totals["electric_bike"] >= threshold)
        ].index.astype(str)
        sub = paired[paired["od_pair"].astype(str).isin(set(keep_pairs))]
        possible = len(keep_pairs) * 2 * 28
        rows.append(
            {
                "min_total_rides_per_type": threshold,
                "od_pairs": len(keep_pairs),
                "possible_paired_rows": possible,
                "actual_paired_rows": len(sub),
                "share_possible_paired_rows": float(len(sub) / possible) if possible else np.nan,
                "classic_paired_rows": int((sub["rideable_type"] == "classic_bike").sum()),
                "ebike_paired_rows": int((sub["rideable_type"] == "electric_bike").sum()),
                "median_pre_rides_per_paired_cell": float(sub["rides_pre"].median()) if len(sub) else np.nan,
                "median_post_rides_per_paired_cell": float(sub["rides_post"].median()) if len(sub) else np.nan,
                "p75_pre_rides_per_paired_cell": float(sub["rides_pre"].quantile(0.75)) if len(sub) else np.nan,
                "p75_post_rides_per_paired_cell": float(sub["rides_post"].quantile(0.75)) if len(sub) else np.nan,
                "p90_pre_rides_per_paired_cell": float(sub["rides_pre"].quantile(0.90)) if len(sub) else np.nan,
                "p90_post_rides_per_paired_cell": float(sub["rides_post"].quantile(0.90)) if len(sub) else np.nan,
            }
        )
    return pd.DataFrame(rows)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    trips = read_filtered_trips()
    daily, pair, distributions = summarize_daily_counts(trips)
    paired_thresholds = paired_threshold_diagnostics(trips)

    summary_rows = []
    for ride_type, sub in pair.groupby("rideable_type"):
        pre_post = sub[sub["appears_pre_and_post"]]
        every_day = sub[sub["appears_every_day"]]
        summary_rows.append(
            {
                "rideable_type": ride_type,
                "window_days": N_DAYS,
                "total_rides": int(trips.loc[trips["rideable_type"] == ride_type, "ride_id"].count()),
                "od_pairs_observed": int(len(sub)),
                "od_pairs_pre_and_post": int(len(pre_post)),
                "od_pairs_every_day": int(len(every_day)),
                "observed_od_days": int(daily.loc[daily["rideable_type"] == ride_type].shape[0]),
                "mean_observed_days_per_pair": float(sub["observed_days"].mean()),
                "median_observed_days_per_pair": float(sub["observed_days"].median()),
                "mean_rides_per_observed_od_day": float(
                    daily.loc[daily["rideable_type"] == ride_type, "rides"].mean()
                ),
                "median_rides_per_observed_od_day": float(
                    daily.loc[daily["rideable_type"] == ride_type, "rides"].median()
                ),
                "mean_rides_per_observed_od_day_pre_post_pairs": float(
                    daily.merge(pre_post[["rideable_type", "od_pair"]], on=["rideable_type", "od_pair"])
                    ["rides"]
                    .mean()
                ),
                "median_rides_per_observed_od_day_pre_post_pairs": float(
                    daily.merge(pre_post[["rideable_type", "od_pair"]], on=["rideable_type", "od_pair"])
                    ["rides"]
                    .median()
                ),
            }
        )

    summary_rows.append(
        {
            "rideable_type": "both_ride_types",
            "window_days": N_DAYS,
            "total_rides": int(len(trips)),
            "od_pairs_observed": int(pair["od_pair"].nunique()),
            "od_pairs_pre_and_post": int(
                pair[pair["appears_pre_and_post"]].groupby("od_pair")["rideable_type"].nunique().eq(2).sum()
            ),
            "od_pairs_every_day": int(
                pair[pair["appears_every_day"]].groupby("od_pair")["rideable_type"].nunique().eq(2).sum()
            ),
            "observed_od_days": int(daily.groupby(["od_pair", "date"]).ngroups),
            "mean_observed_days_per_pair": np.nan,
            "median_observed_days_per_pair": np.nan,
            "mean_rides_per_observed_od_day": float(daily["rides"].mean()),
            "median_rides_per_observed_od_day": float(daily["rides"].median()),
            "mean_rides_per_observed_od_day_pre_post_pairs": np.nan,
            "median_rides_per_observed_od_day_pre_post_pairs": np.nan,
        }
    )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(SUMMARY_OUT, index=False)
    distributions[distributions["distribution"] == "daily"].to_csv(DAILY_DIST_OUT, index=False)
    distributions[distributions["distribution"] == "pair"].to_csv(PAIR_DIST_OUT, index=False)
    paired_thresholds.to_csv(PAIRED_THRESHOLDS_OUT, index=False)

    print(f"Wrote {SUMMARY_OUT}")
    print(f"Wrote {DAILY_DIST_OUT}")
    print(f"Wrote {PAIR_DIST_OUT}")
    print(f"Wrote {PAIRED_THRESHOLDS_OUT}")
    print(summary.to_string(index=False))
    print("\nPaired threshold diagnostics")
    print(paired_thresholds.to_string(index=False))


if __name__ == "__main__":
    main()
