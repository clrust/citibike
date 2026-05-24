"""
Build a station-hour Divvy demand panel for Chicago.
"""

from __future__ import annotations

from panel_utils import build_city_panel


def main() -> None:
    build_city_panel(
        description=__doc__ or "",
        raw_subdir="divvy",
        out_name="02_divvy.csv",
        file_tokens=("divvy",),
        column_map={
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
        city="chicago",
        system="divvy",
        treated_city=0,
    )


if __name__ == "__main__":
    main()
