"""
Estimate the station-weighted AIPTW ATT for matched station-hour e-bike trip changes.
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
