"""
Build a station-hour Divvy demand panel.

Defaults mirror the Citi Bike build: September 2025 and November 2025. Change
the window with:

    python3 build/02_divvy.py --months 2025-09 2025-11

Expected raw files can be CSVs or ZIPs under data_raw/divvy/ or data_raw/.
The script searches for files containing each YYYYMM token, such as:

    data_raw/divvy/202509-divvy-tripdata.zip
    data_raw/202511-divvy-tripdata.csv
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

import pandas as pd


DEFAULT_MONTHS = ("2025-09", "2025-11")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--raw-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "divvy")
    parser.add_argument("--fallback-raw-dir", type=Path, default=PROJECT_ROOT / "data_raw")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data_clean" / "02_divvy.csv")
    return parser.parse_args()


def month_token(month: str) -> str:
    return pd.Period(month, freq="M").strftime("%Y%m")


def month_periods(months: list[str]) -> list[pd.Period]:
    return sorted(pd.Period(m, freq="M") for m in months)


def requested_hours(months: list[str]) -> pd.DataFrame:
    hours: list[pd.Timestamp] = []
    for period in month_periods(months):
        hours.extend(pd.date_range(period.start_time, period.end_time.floor("s").floor("h"), freq="h"))
    return pd.DataFrame({"station_hour": pd.DatetimeIndex(hours)})


def find_month_files(raw_dirs: list[Path], months: list[str], city_hint: str) -> list[Path]:
    files: list[Path] = []
    for month in months:
        token = month_token(month)
        hinted_matches: list[Path] = []
        generic_matches: list[Path] = []
        for raw_dir in raw_dirs:
            if not raw_dir.exists():
                continue
            hinted_matches.extend(
                p
                for p in raw_dir.rglob("*")
                if p.is_file()
                and token in p.name
                and p.suffix.lower() in {".csv", ".zip"}
                and city_hint.lower() in p.name.lower()
            )
            generic_matches.extend(
                p
                for p in raw_dir.rglob("*")
                if p.is_file()
                and token in p.name
                and p.suffix.lower() in {".csv", ".zip"}
            )
        matches = hinted_matches or generic_matches
        if not matches:
            searched = ", ".join(str(d) for d in raw_dirs)
            raise FileNotFoundError(f"No Divvy raw file found for {month} in {searched}")
        files.extend(sorted(set(matches)))
    return sorted(set(files))


def csv_sources(path: Path) -> list[str]:
    if path.suffix.lower() != ".zip":
        return [str(path)]
    with zipfile.ZipFile(path) as archive:
        names = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".csv")
            and not Path(name).name.startswith("._")
            and "__macosx/" not in name.lower()
        ]
    if not names:
        raise ValueError(f"No CSV found inside {path}")
    return names


def standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    required = {
        "started_at",
        "rideable_type",
        "start_station_id",
        "start_station_name",
    }
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Missing expected Divvy columns: {sorted(missing)}")

    keep = [
        "started_at",
        "ended_at",
        "rideable_type",
        "start_station_id",
        "start_station_name",
        "start_lat",
        "start_lng",
    ]
    keep = [c for c in keep if c in df.columns]
    out = df.loc[:, keep].copy()
    out["started_at"] = pd.to_datetime(out["started_at"], errors="coerce")
    out["start_station_id"] = out["start_station_id"].astype("string")
    out["start_station_name"] = out["start_station_name"].astype("string")
    if "ended_at" in out.columns:
        out["ended_at"] = pd.to_datetime(out["ended_at"], errors="coerce")
        duration = (out["ended_at"] - out["started_at"]).dt.total_seconds() / 60
        out["duration_minutes"] = duration.where(duration.between(0, 24 * 60))
    else:
        out["duration_minutes"] = pd.NA
    return out


def aggregate_file(path: Path, months: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    pieces: list[pd.DataFrame] = []
    station_pieces: list[pd.DataFrame] = []
    requested = set(str(p) for p in month_periods(months))

    for source in csv_sources(path):
        if path.suffix.lower() == ".zip":
            zip_archive = zipfile.ZipFile(path)
            csv_handle = zip_archive.open(source)
        else:
            zip_archive = None
            csv_handle = source

        try:
            reader = pd.read_csv(csv_handle, chunksize=500_000, low_memory=False)
            for chunk in reader:
                chunk = standardize_columns(chunk)
                chunk = chunk[chunk["started_at"].dt.to_period("M").astype(str).isin(requested)]
                chunk = chunk.dropna(subset=["started_at", "start_station_id", "start_station_name"])
                if chunk.empty:
                    continue

                chunk["station_hour"] = chunk["started_at"].dt.floor("h")
                chunk["is_ebike"] = chunk["rideable_type"].str.contains("electric", case=False, na=False)
                chunk["is_classic"] = ~chunk["is_ebike"]

                group_cols = ["station_hour", "start_station_id", "start_station_name"]
                agg_spec = {
                    "trip_count": ("rideable_type", "size"),
                    "ebike_trip_count": ("is_ebike", "sum"),
                    "classic_trip_count": ("is_classic", "sum"),
                    "mean_duration_minutes": ("duration_minutes", "mean"),
                }
                if "start_lat" in chunk.columns:
                    agg_spec["start_lat"] = ("start_lat", "mean")
                if "start_lng" in chunk.columns:
                    agg_spec["start_lng"] = ("start_lng", "mean")
                agg = chunk.groupby(group_cols, dropna=False).agg(**agg_spec).reset_index()
                pieces.append(agg)

                station_cols = ["start_station_id", "start_station_name"]
                for col in ("start_lat", "start_lng"):
                    if col in chunk.columns:
                        station_cols.append(col)
                station_pieces.append(chunk.loc[:, station_cols].drop_duplicates())
        finally:
            if zip_archive is not None:
                csv_handle.close()
                zip_archive.close()

    if not pieces:
        return pd.DataFrame(), pd.DataFrame()
    return pd.concat(pieces, ignore_index=True), pd.concat(station_pieces, ignore_index=True)


def build_panel(aggregates: pd.DataFrame, stations: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    station_cols = ["start_station_id", "start_station_name"]
    required_months = {str(period) for period in month_periods(months)}
    station_months = aggregates.loc[:, station_cols + ["station_hour"]].copy()
    station_months["month"] = station_months["station_hour"].dt.to_period("M").astype(str)
    complete_stations = (
        station_months[station_months["month"].isin(required_months)]
        .drop_duplicates(station_cols + ["month"])
        .groupby(station_cols, dropna=False)["month"]
        .nunique()
    )
    complete_stations = complete_stations[complete_stations == len(required_months)].reset_index()[station_cols]

    coord_aggs = {}
    if "start_lat" in stations.columns:
        coord_aggs["start_lat"] = "mean"
    if "start_lng" in stations.columns:
        coord_aggs["start_lng"] = "mean"

    if coord_aggs:
        station_index = stations.groupby(station_cols, dropna=False).agg(coord_aggs).reset_index()
    else:
        station_index = stations.loc[:, station_cols].drop_duplicates()
    station_index = station_index.merge(complete_stations, on=station_cols, how="inner")
    station_index = station_index.sort_values(station_cols)
    hours = requested_hours(months)
    panel = station_index.merge(hours, how="cross")

    numeric_aggs = {
        "trip_count": "sum",
        "ebike_trip_count": "sum",
        "classic_trip_count": "sum",
        "mean_duration_minutes": "mean",
    }
    for coord in ("start_lat", "start_lng"):
        if coord in aggregates.columns:
            numeric_aggs[coord] = "mean"

    collapsed = (
        aggregates.groupby(["station_hour", "start_station_id", "start_station_name"], dropna=False)
        .agg(numeric_aggs)
        .reset_index()
    )
    panel = panel.merge(collapsed, on=["station_hour", "start_station_id", "start_station_name"], how="left", suffixes=("", "_obs"))

    for col in ("trip_count", "ebike_trip_count", "classic_trip_count"):
        panel[col] = panel[col].fillna(0).astype("int64")
    panel["mean_duration_minutes"] = panel["mean_duration_minutes"].where(panel["trip_count"] > 0)
    for coord in ("start_lat", "start_lng"):
        obs_col = f"{coord}_obs"
        if obs_col in panel.columns:
            panel[coord] = panel[coord].fillna(panel[obs_col])
            panel = panel.drop(columns=[obs_col])

    panel["city"] = "chicago"
    panel["system"] = "divvy"
    panel["station_uid"] = panel["city"] + ":" + panel["start_station_id"].astype("string")
    panel["treated_city"] = 0
    panel["post_speed_limit"] = (panel["station_hour"] >= pd.Timestamp("2025-10-24")).astype("int8")
    panel["month"] = panel["station_hour"].dt.to_period("M").astype(str)
    panel["date"] = panel["station_hour"].dt.date.astype(str)
    panel["hour"] = panel["station_hour"].dt.hour
    panel["day_of_week"] = panel["station_hour"].dt.dayofweek
    return panel.sort_values(["station_hour", "start_station_id"]).reset_index(drop=True)


def main() -> None:
    args = parse_args()
    files = find_month_files([args.raw_dir, args.fallback_raw_dir], args.months, "divvy")

    aggregates: list[pd.DataFrame] = []
    stations: list[pd.DataFrame] = []
    for path in files:
        agg, station = aggregate_file(path, args.months)
        if not agg.empty:
            aggregates.append(agg)
            stations.append(station)
    if not aggregates:
        raise RuntimeError("No Divvy trips remained after filtering to the requested months.")

    panel = build_panel(pd.concat(aggregates, ignore_index=True), pd.concat(stations, ignore_index=True), args.months)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out, index=False)
    print(f"Wrote {len(panel):,} Divvy station-hour rows to {args.out}")


if __name__ == "__main__":
    main()
