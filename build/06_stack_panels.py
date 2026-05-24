"""
Stack city station-hour panels into one all-cities panel.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = (
    PROJECT_ROOT / "data_clean" / "01_citibike.csv",
    PROJECT_ROOT / "data_clean" / "02_divvy.csv",
    PROJECT_ROOT / "data_clean" / "03_indego.csv",
    PROJECT_ROOT / "data_clean" / "04_bluebikes.csv",
    PROJECT_ROOT / "data_clean" / "05_capital_bikeshare.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", nargs="+", type=Path, default=list(DEFAULT_INPUTS))
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "data_clean" / "06_station_hour_panel.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    missing = [path for path in args.inputs if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing panel file(s): {', '.join(str(path) for path in missing)}")

    pieces = [pd.read_csv(path, low_memory=False) for path in args.inputs]
    panel = pd.concat(pieces, ignore_index=True)
    panel["station_hour"] = pd.to_datetime(panel["station_hour"], errors="coerce")
    if "station_uid" not in panel.columns:
        panel["station_uid"] = panel["city"].astype(str) + ":" + panel["start_station_id"].astype(str)
    panel = panel.sort_values(["city", "station_hour", "station_uid"]).reset_index(drop=True)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    panel.to_csv(args.out, index=False)
    print(f"Wrote {len(panel):,} all-city station-hour rows to {args.out}")


if __name__ == "__main__":
    main()
