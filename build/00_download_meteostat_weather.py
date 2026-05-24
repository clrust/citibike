"""
Download hourly weather from Meteostat for the DiD build.

Default output files are compatible with build/07_weather_merge.py:

    python3 build/00_download_meteostat_weather.py

The default months are September 2025 and November 2025. Change them with:

    python3 build/00_download_meteostat_weather.py --months 2025-08 2025-09 2025-11 2025-12

Requires:

    python3 -m pip install meteostat pandas
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from panel_utils import write_csv_atomic


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MONTHS = ("2025-09", "2025-11")

STATIONS = {
    "nyc": {
        "name": "NYC Central Park",
        "latitude": 40.7829,
        "longitude": -73.9654,
        "timezone": "America/New_York",
        "preferred_icaos": ("KNYC",),
        "out": "nyc_weather.csv",
    },
    "chicago": {
        "name": "Chicago O'Hare",
        "latitude": 41.9742,
        "longitude": -87.9073,
        "timezone": "America/Chicago",
        "preferred_icaos": ("KORD",),
        "out": "chicago_weather.csv",
    },
    "philadelphia": {
        "name": "Philadelphia International Airport",
        "latitude": 39.8729,
        "longitude": -75.2437,
        "timezone": "America/New_York",
        "preferred_icaos": ("KPHL",),
        "out": "philadelphia_weather.csv",
    },
    "boston": {
        "name": "Boston Logan International Airport",
        "latitude": 42.3656,
        "longitude": -71.0096,
        "timezone": "America/New_York",
        "preferred_icaos": ("KBOS",),
        "out": "boston_weather.csv",
    },
    "washington_dc": {
        "name": "Washington Reagan National Airport",
        "latitude": 38.8512,
        "longitude": -77.0402,
        "timezone": "America/New_York",
        "preferred_icaos": ("KDCA",),
        "out": "washington_dc_weather.csv",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", nargs="+", default=list(DEFAULT_MONTHS))
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "data_raw" / "weather")
    parser.add_argument("--max-station-distance-km", type=float, default=50)
    return parser.parse_args()


def month_periods(months: list[str]) -> list[pd.Period]:
    return sorted(pd.Period(month, freq="M") for month in months)


def utc_bounds_for_months(months: list[str], local_timezone: str) -> tuple[datetime, datetime]:
    periods = month_periods(months)
    tz = ZoneInfo(local_timezone)
    local_start = periods[0].start_time.to_pydatetime().replace(tzinfo=tz)
    local_end = periods[-1].end_time.floor("s").to_pydatetime().replace(tzinfo=tz)
    return (
        local_start.astimezone(timezone.utc).replace(tzinfo=None),
        local_end.astimezone(timezone.utc).replace(tzinfo=None),
    )


def requested_local_hours(months: list[str], local_timezone: str) -> pd.DataFrame:
    tz = ZoneInfo(local_timezone)
    hours: list[pd.Timestamp] = []
    for period in month_periods(months):
        local_start = pd.Timestamp(period.start_time, tz=tz)
        local_end = pd.Timestamp(period.end_time.floor("s").floor("h"), tz=tz)
        hours.extend(pd.date_range(local_start, local_end, freq="h"))
    return pd.DataFrame({"station_hour": pd.DatetimeIndex(hours).tz_localize(None)})


def select_station(station_config: dict, start_utc: datetime, end_utc: datetime, max_distance_km: float):
    try:
        from meteostat import Point, Provider, stations
    except ImportError:
        Point = None
        Provider = None
        stations = None

    if stations is not None:
        nearby = stations.nearby(
            Point(station_config["latitude"], station_config["longitude"]),
            radius=max_distance_km * 1000,
            limit=25,
        )
        if not nearby.empty:
            inventory = stations.inventory(nearby.index.to_list(), providers=[Provider.HOURLY]).df
            if inventory is not None and not inventory.empty:
                inventory = inventory.reset_index()
                start_date = pd.Timestamp(start_utc.date())
                end_date = pd.Timestamp(end_utc.date())
                has_requested_inventory = (
                    (pd.to_datetime(inventory["start"]) <= end_date)
                    & (pd.to_datetime(inventory["end"]) >= start_date)
                )
                nearby = nearby[nearby.index.isin(inventory.loc[has_requested_inventory, "station"])]

        if nearby.empty:
            raise RuntimeError(f"No Meteostat hourly stations found near {station_config['name']}")

        nearby = nearby.copy()
        nearby["icao"] = pd.NA
        for station_id in nearby.index:
            meta = stations.meta(station_id)
            if meta is not None:
                nearby.loc[station_id, "icao"] = (
                    meta.identifiers.get("icao")
                    or meta.identifiers.get("ICAO")
                    or meta.identifiers.get("icao_code")
                )
    else:
        from meteostat import Stations

        nearby = (
            Stations()
            .nearby(station_config["latitude"], station_config["longitude"])
            .inventory("hourly", (start_utc, end_utc))
            .fetch(25)
        )

    if nearby.empty:
        raise RuntimeError(f"No Meteostat hourly stations found near {station_config['name']}")

    candidates = nearby
    nearby = candidates[candidates["distance"] <= max_distance_km * 1000].copy()
    if nearby.empty:
        nearest = candidates.iloc[0]
        distance_km = nearest["distance"] / 1000
        raise RuntimeError(
            f"Nearest station to {station_config['name']} is {distance_km:.1f} km away, "
            f"above --max-station-distance-km={max_distance_km}."
        )

    for icao in station_config["preferred_icaos"]:
        preferred = nearby[nearby.get("icao", pd.Series(dtype=str)).fillna("") == icao]
        if not preferred.empty:
            return preferred.index[0], preferred.iloc[0]

    return nearby.index[0], nearby.iloc[0]


def fetch_city_weather(city: str, station_config: dict, months: list[str], max_distance_km: float) -> pd.DataFrame:
    try:
        from meteostat import hourly
    except ImportError:
        hourly = None

    start_utc, end_utc = utc_bounds_for_months(months, station_config["timezone"])
    station_id, station_meta = select_station(station_config, start_utc, end_utc, max_distance_km)

    if hourly is not None:
        weather = hourly(station_id, start_utc, end_utc).fetch()
    else:
        from meteostat import Hourly

        weather = Hourly(station_id, start_utc, end_utc).fetch()

    weather = pd.DataFrame() if weather is None else weather.reset_index()
    if weather.empty:
        raise RuntimeError(f"Meteostat returned no hourly rows for {station_config['name']} ({station_id})")

    local_tz = ZoneInfo(station_config["timezone"])
    weather["station_hour"] = (
        pd.to_datetime(weather["time"], utc=True)
        .dt.tz_convert(local_tz)
        .dt.tz_localize(None)
    )

    weather = weather.rename(
        columns={
            "temp": "temp_c",
            "dwpt": "dew_point_c",
            "rhum": "relative_humidity",
            "prcp": "precip_mm",
            "snow": "snow_mm",
            "snwd": "snow_mm",
            "wdir": "wind_direction_degrees",
            "wspd": "wind_speed_kph",
            "wpgt": "wind_peak_gust_kph",
            "pres": "pressure_hpa",
            "tsun": "sunshine_minutes",
            "coco": "weather_condition_code",
        }
    )

    if "temp_c" in weather:
        weather["temp_f"] = weather["temp_c"] * 9 / 5 + 32
    if "dew_point_c" in weather:
        weather["dew_point_f"] = weather["dew_point_c"] * 9 / 5 + 32
    if "precip_mm" in weather:
        weather["precip_in"] = weather["precip_mm"] / 25.4
    if "snow_mm" in weather:
        weather["snow_in"] = weather["snow_mm"] / 25.4
    if "wind_speed_kph" in weather:
        weather["wind_speed_mph"] = weather["wind_speed_kph"] * 0.621371
    if "wind_peak_gust_kph" in weather:
        weather["wind_peak_gust_mph"] = weather["wind_peak_gust_kph"] * 0.621371

    keep = [
        "station_hour",
        "temp_f",
        "temp_c",
        "dew_point_f",
        "dew_point_c",
        "relative_humidity",
        "precip_in",
        "precip_mm",
        "snow_in",
        "snow_mm",
        "wind_speed_mph",
        "wind_speed_kph",
        "wind_peak_gust_mph",
        "wind_peak_gust_kph",
        "wind_direction_degrees",
        "pressure_hpa",
        "weather_condition_code",
    ]
    keep = [col for col in keep if col in weather.columns]
    weather = weather.loc[:, keep]
    weather = requested_local_hours(months, station_config["timezone"]).merge(weather, on="station_hour", how="left")

    weather["weather_source"] = "meteostat"
    weather["weather_city"] = city
    weather["weather_station_id"] = station_id
    weather["weather_station_name"] = station_meta.get("name")
    weather["weather_station_icao"] = station_meta.get("icao")
    weather["weather_station_distance_km"] = station_meta.get("distance", pd.NA) / 1000
    return weather.sort_values("station_hour")


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for city, config in STATIONS.items():
        weather = fetch_city_weather(city, config, args.months, args.max_station_distance_km)
        out = args.out_dir / config["out"]
        write_csv_atomic(weather, out)
        station = weather["weather_station_id"].dropna().iloc[0]
        rows_with_temp = weather["temp_f"].notna().sum() if "temp_f" in weather else 0
        print(f"Wrote {len(weather):,} {city} rows to {out} using Meteostat station {station}")
        print(f"Rows with non-missing temperature: {rows_with_temp:,}")


if __name__ == "__main__":
    main()
