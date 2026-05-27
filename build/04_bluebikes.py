"""
Build a station-hour Bluebikes demand panel for Boston.
"""

from __future__ import annotations

from panel_utils import build_city_panel


def main() -> None:
    build_city_panel(
        description=__doc__ or "",
        raw_subdir="bluebike",
        out_name="og_main_spec_sept_nov/04_bluebikes.csv",
        file_tokens=("bluebike", "bluebikes"),
        column_map={
            "started_at": "started_at",
            "ended_at": "ended_at",
            "rideable_type": "rideable_type",
            "start_station_id": "start_station_id",
            "start_station_name": "start_station_name",
            "start_lat": "start_lat",
            "start_lng": "start_lng",
        },
        city="boston",
        system="bluebikes",
        treated_city=0,
    )


if __name__ == "__main__":
    main()
