from __future__ import annotations

import argparse
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_MONTHS = ("2025-09", "2025-11")
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def month_token(month: str) -> str:
    return pd.Period(month, freq="M").strftime("%Y%m")


def month_periods(months: list[str]) -> list[pd.Period]:
    return sorted(pd.Period(m, freq="M") for m in months)


def requested_hours(months: list[str]) -> pd.DataFrame:
    hours: list[pd.Timestamp] = []
    for period in month_periods(months):
        hours.extend(pd.date_range(period.start_time, period.end_time.floor("s").floor("h"), freq="h"))
    return pd.DataFrame({"station_hour": pd.DatetimeIndex(hours)})


def find_month_files(raw_dirs: list[Path], months: list[str], file_tokens: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for month in months:
        yyyymm = month_token(month)
        yyyy_q = f"{yyyymm[:4]}-q{pd.Period(month, freq='M').quarter}"
        month_matches: list[Path] = []
        quarter_matches: list[Path] = []
        for raw_dir in raw_dirs:
            if not raw_dir.exists():
                continue
            for path in raw_dir.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in {".csv", ".zip"}:
                    continue
                name = path.name.lower()
                if not any(token in name for token in file_tokens):
                    continue
                if yyyymm in name:
                    month_matches.append(path)
                elif yyyy_q in name:
                    quarter_matches.append(path)
        matches = month_matches or quarter_matches
        if not matches:
            searched = ", ".join(str(d) for d in raw_dirs)
            raise FileNotFoundError(f"No raw file found for {month} with tokens {file_tokens} in {searched}")
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


def standardize_columns(df: pd.DataFrame, column_map: dict[str, str]) -> pd.DataFrame:
    df = df.rename(columns={c: c.strip().lower() for c in df.columns})
    missing = sorted(source for source in column_map if source not in df.columns)
    if missing:
        raise ValueError(f"Missing expected raw columns: {missing}")

    out = df.loc[:, list(column_map)].rename(columns=column_map).copy()
    out["started_at"] = pd.to_datetime(out["started_at"], errors="coerce")
    out["start_station_id"] = out["start_station_id"].astype("string")
    if "start_station_name" not in out:
        out["start_station_name"] = out["start_station_id"]
    out["start_station_name"] = out["start_station_name"].astype("string").fillna(out["start_station_id"])

    if "ended_at" in out.columns:
        out["ended_at"] = pd.to_datetime(out["ended_at"], errors="coerce")
        duration = (out["ended_at"] - out["started_at"]).dt.total_seconds() / 60
        out["duration_minutes"] = duration.where(duration.between(0, 24 * 60))
    elif "duration_minutes" in out.columns:
        out["duration_minutes"] = pd.to_numeric(out["duration_minutes"], errors="coerce")
        out["duration_minutes"] = out["duration_minutes"].where(out["duration_minutes"].between(0, 24 * 60))
    else:
        out["duration_minutes"] = pd.NA

    return out


def aggregate_file(path: Path, months: list[str], column_map: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
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
                chunk = standardize_columns(chunk, column_map)
                chunk = chunk[chunk["started_at"].dt.to_period("M").astype(str).isin(requested)]
                chunk = chunk.dropna(subset=["started_at", "start_station_id", "start_station_name"])
                if chunk.empty:
                    continue

                chunk["station_hour"] = chunk["started_at"].dt.floor("h")
                chunk["is_ebike"] = chunk["rideable_type"].str.contains("electric", case=False, na=False)
                chunk["is_classic"] = ~chunk["is_ebike"]

                group_cols = ["station_hour", "start_station_id", "start_station_name"]
                agg_spec: dict[str, Any] = {
                    "trip_count": ("rideable_type", "size"),
                    "ebike_trip_count": ("is_ebike", "sum"),
                    "classic_trip_count": ("is_classic", "sum"),
                    "mean_duration_minutes": ("duration_minutes", "mean"),
                }
                if "start_lat" in chunk.columns:
                    agg_spec["start_lat"] = ("start_lat", "mean")
                if "start_lng" in chunk.columns:
                    agg_spec["start_lng"] = ("start_lng", "mean")
                pieces.append(chunk.groupby(group_cols, dropna=False).agg(**agg_spec).reset_index())

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


def build_panel(
    aggregates: pd.DataFrame,
    stations: pd.DataFrame,
    months: list[str],
    city: str,
    system: str,
    treated_city: int,
    event_date: str,
) -> pd.DataFrame:
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
    panel = station_index.merge(requested_hours(months), how="cross")

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

    panel["city"] = city
    panel["system"] = system
    panel["station_uid"] = panel["city"] + ":" + panel["start_station_id"].astype("string")
    panel["treated_city"] = treated_city
    panel["post_speed_limit"] = (panel["station_hour"] >= pd.Timestamp(event_date)).astype("int8")
    panel["month"] = panel["station_hour"].dt.to_period("M").astype(str)
    panel["date"] = panel["station_hour"].dt.date.astype(str)
    panel["hour"] = panel["station_hour"].dt.hour
    panel["day_of_week"] = panel["station_hour"].dt.dayofweek
    return panel.sort_values(["station_hour", "start_station_id"]).reset_index(drop=True)


def parse_city_args(description: str, raw_dir: Path, out: Path) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--raw-dir", type=Path, default=raw_dir)
    parser.add_argument("--fallback-raw-dir", type=Path, default=PROJECT_ROOT / "data_raw")
    parser.add_argument("--out", type=Path, default=out)
    parser.add_argument("--event-date", default="2025-10-24")
    return parser.parse_args()


def build_city_panel(
    *,
    description: str,
    raw_subdir: str,
    out_name: str,
    file_tokens: tuple[str, ...],
    column_map: dict[str, str],
    city: str,
    system: str,
    treated_city: int,
) -> None:
    args = parse_city_args(
        description,
        PROJECT_ROOT / "data_raw" / raw_subdir,
        PROJECT_ROOT / "data_clean" / out_name,
    )
    files = find_month_files([args.raw_dir, args.fallback_raw_dir], args.months, file_tokens)

    aggregates: list[pd.DataFrame] = []
    stations: list[pd.DataFrame] = []
    for path in files:
        agg, station = aggregate_file(path, args.months, column_map)
        if not agg.empty:
            aggregates.append(agg)
            stations.append(station)
    if not aggregates:
        raise RuntimeError(f"No {system} trips remained after filtering to the requested months.")

    panel = build_panel(
        pd.concat(aggregates, ignore_index=True),
        pd.concat(stations, ignore_index=True),
        args.months,
        city,
        system,
        treated_city,
        args.event_date,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out, index=False)
    print(f"Wrote {len(panel):,} {system} station-hour rows to {args.out}")
