"""
Combine sensitivity result CSVs into one summary table.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from aiptw_common import PROJECT_ROOT


RESULTS_DIR = PROJECT_ROOT / "results" / "sensitivities"
SUMMARY_FILES = (
    "leave_one_control_out_summary.csv",
    "one_control_city_summary.csv",
    "control_city_placebos_summary.csv",
    "aug_sep_2025_placebo_summary.csv",
    "sep_nov_2024_placebo_summary.csv",
    "classic_rides_robustness_summary.csv",
)


def main() -> None:
    pieces = []
    for filename in SUMMARY_FILES:
        path = RESULTS_DIR / filename
        if path.exists():
            frame = pd.read_csv(path)
            frame["source_file"] = filename
            pieces.append(frame)
    if not pieces:
        raise FileNotFoundError(f"No sensitivity summary files found in {RESULTS_DIR}")
    out = RESULTS_DIR / "sensitivity_summary.csv"
    pd.concat(pieces, ignore_index=True, sort=False).to_csv(out, index=False)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
