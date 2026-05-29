"""
Plot the rolling assumed-treatment-date AIPTW estimates.

The plotted estimates come from results/rolling_att/rolling_att_summary.csv.
They are analytic AIPTW confidence intervals, not bootstrap intervals.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.dates import DateFormatter


RESULTS_DIR = PROJECT_ROOT / "results" / "rolling_att"
FIGURE_DIR = RESULTS_DIR / "figures"
SUMMARY_PATH = RESULTS_DIR / "rolling_att_summary.csv"
PNG_OUT = FIGURE_DIR / "rolling_att_plot.png"
PDF_OUT = FIGURE_DIR / "rolling_att_plot.pdf"
POINTS_PNG_OUT = FIGURE_DIR / "rolling_att_points_errorbars.png"
POINTS_PDF_OUT = FIGURE_DIR / "rolling_att_points_errorbars.pdf"


def main() -> None:
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SUMMARY_PATH, parse_dates=["assumed_treatment_date"])
    df = df.sort_values("assumed_treatment_date")

    yerr = [df["att"] - df["ci_low"], df["ci_high"] - df["att"]]

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.errorbar(
        df["assumed_treatment_date"],
        df["att"],
        yerr=yerr,
        fmt="o-",
        color="#1f4e79",
        ecolor="#7f9db9",
        elinewidth=1.4,
        capsize=3,
        linewidth=2,
        markersize=5,
    )
    ax.axhline(0, color="#555555", linewidth=1, linestyle="--")
    ax.axvline(pd.Timestamp("2025-10-03"), color="#b7791f", linewidth=1.5, linestyle="--")
    ax.axvline(pd.Timestamp("2025-10-24"), color="#a23b3b", linewidth=1.5, linestyle=":")
    ax.text(
        pd.Timestamp("2025-10-03"),
        ax.get_ylim()[1],
        " post window includes Oct 24",
        color="#8a5a16",
        ha="left",
        va="top",
        fontsize=9,
    )
    ax.text(
        pd.Timestamp("2025-10-24"),
        ax.get_ylim()[1],
        " Oct 24",
        color="#7a2c2c",
        ha="left",
        va="top",
        fontsize=10,
    )
    ax.set_title("Rolling Four-Week AIPTW ATT by Assumed Treatment Date")
    ax.set_xlabel("Assumed treatment date")
    ax.set_ylabel("ATT on e-bike trips per station-hour")
    ax.set_xticks(df["assumed_treatment_date"])
    ax.xaxis.set_major_formatter(DateFormatter("%m-%d"))
    ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(PNG_OUT, dpi=200)
    fig.savefig(PDF_OUT)
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {PDF_OUT}")

    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.errorbar(
        df["assumed_treatment_date"],
        df["att"],
        yerr=yerr,
        fmt="o",
        color="#1f4e79",
        ecolor="#7f9db9",
        elinewidth=1.4,
        capsize=3,
        markersize=5,
        linestyle="none",
    )
    ax.axhline(0, color="#555555", linewidth=1, linestyle="--")
    ax.axvline(pd.Timestamp("2025-10-03"), color="#b7791f", linewidth=1.5, linestyle="--")
    ax.axvline(pd.Timestamp("2025-10-24"), color="#a23b3b", linewidth=1.5, linestyle=":")
    ax.text(
        pd.Timestamp("2025-10-03"),
        ax.get_ylim()[1],
        " post window includes Oct 24",
        color="#8a5a16",
        ha="left",
        va="top",
        fontsize=9,
    )
    ax.text(
        pd.Timestamp("2025-10-24"),
        ax.get_ylim()[1],
        " Oct 24",
        color="#7a2c2c",
        ha="left",
        va="top",
        fontsize=10,
    )
    ax.set_title("Rolling Four-Week AIPTW ATT by Assumed Treatment Date")
    ax.set_xlabel("Assumed treatment date")
    ax.set_ylabel("ATT on e-bike trips per station-hour")
    ax.set_xticks(df["assumed_treatment_date"])
    ax.xaxis.set_major_formatter(DateFormatter("%m-%d"))
    ax.grid(axis="y", color="#dddddd", linewidth=0.8)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(POINTS_PNG_OUT, dpi=200)
    fig.savefig(POINTS_PDF_OUT)
    print(f"Wrote {POINTS_PNG_OUT}")
    print(f"Wrote {POINTS_PDF_OUT}")


if __name__ == "__main__":
    main()
