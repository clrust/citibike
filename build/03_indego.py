"""
Build a station-hour Indego demand panel for Philadelphia.
"""

from __future__ import annotations

from panel_utils import build_city_panel


def main() -> None:
    build_city_panel(
        description=__doc__ or "",
        raw_subdir="indego",
        out_name="og_main_spec_sept_nov/03_indego.csv",
        file_tokens=("indego",),
        column_map={
            "start_time": "started_at",
            "end_time": "ended_at",
            "bike_type": "rideable_type",
            "start_station": "start_station_id",
            "start_lat": "start_lat",
            "start_lon": "start_lng",
            "duration": "duration_minutes",
        },
        city="philadelphia",
        system="indego",
        treated_city=0,
    )


if __name__ == "__main__":
    main()
