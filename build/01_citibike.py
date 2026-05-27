"""
Build a station-hour Citi Bike demand panel for NYC.
"""

from __future__ import annotations

from panel_utils import build_city_panel


def main() -> None:
    build_city_panel(
        description=__doc__ or "",
        raw_subdir="citi_bike",
        out_name="og_main_spec_sept_nov/01_citibike.csv",
        file_tokens=("citibike",),
        exclude_prefixes=("jc-",),
        column_map={
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
        city="nyc",
        system="citibike",
        treated_city=1,
    )


if __name__ == "__main__":
    main()
