"""
Estimate the station-weighted AIPTW ATT for paired station-hour ride changes.

Default window: September 1-21, 2025 versus November 3-23, 2025, unless
overridden by command-line arguments. Default outcome: ebike_trip_count.
Default X covariates: paired differences in continuous weather variables plus
pre/post coarse weather-condition indicators. Time-slot or daylight controls
are included only when the corresponding command-line flags are passed.
"""

from __future__ import annotations

from aiptw_common import parse_args, run_analysis


def main() -> None:
    config = parse_args(
        description=__doc__ or "",
        estimand="ATT for the average treated NYC station",
        station_weighted=True,
    )
    run_analysis(config)


if __name__ == "__main__":
    main()
