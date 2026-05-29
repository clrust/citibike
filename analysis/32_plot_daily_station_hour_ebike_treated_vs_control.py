"""
Plot daily average e-bike rides per retained station-hour.

This is a descriptive plot, not a causal estimate. It reproduces the idea of
the paper/example_average_station_day_ebike_rides.jpeg figure with cleaner
styling and labels. The plotted outcome is the daily mean of ebike_trip_count
across retained station-hours, separately for NYC and pooled controls.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.dates import DateFormatter, WeekdayLocator  # noqa: E402


INPUT_PATH = PROJECT_ROOT / "data_clean" / "main_spec" / "11_sharp_window_station_hour_panel_weather.csv"
OUT_DIR = PROJECT_ROOT / "figures" / "descriptive_ridership" / "day_level"
DATA_OUT = PROJECT_ROOT / "figures" / "descriptive_ridership" / "data" / "daily_station_hour_ebike_treated_vs_control.csv"
PNG_OUT = OUT_DIR / "daily_station_hour_ebike_treated_vs_control.png"
PDF_OUT = OUT_DIR / "daily_station_hour_ebike_treated_vs_control.pdf"

TREATMENT_DATE = pd.Timestamp("2025-10-24")
PRE_START = pd.Timestamp("2025-09-26")
PRE_END = pd.Timestamp("2025-10-23")
POST_END = pd.Timestamp("2025-11-20")


def load_daily_average() -> pd.DataFrame:
    """Aggregate the main-spec station-hour panel to daily treated/control means."""

    usecols = ["city", "station_hour", "ebike_trip_count", "station_uid"]
    panel = pd.read_csv(INPUT_PATH, usecols=usecols, parse_dates=["station_hour"], low_memory=False)
    panel["date"] = panel["station_hour"].dt.normalize()
    panel["group"] = panel["city"].eq("nyc").map({True: "NYC", False: "Pooled controls"})

    daily = (
        panel.groupby(["group", "date"], as_index=False)
        .agg(
            mean_ebike_per_station_hour=("ebike_trip_count", "mean"),
            total_ebike_trips=("ebike_trip_count", "sum"),
            station_hours=("ebike_trip_count", "size"),
            stations=("station_uid", "nunique"),
        )
        .sort_values(["group", "date"])
    )
    daily["period"] = daily["date"].lt(TREATMENT_DATE).map({True: "Pre", False: "Post"})
    return daily


def plot_daily_average(daily: pd.DataFrame) -> None:
    """Create a publication-oriented NYC versus pooled-controls line plot."""

    colors = {"NYC": "#1f4e79", "Pooled controls": "#6b7280"}
    fig, ax = plt.subplots(figsize=(10.5, 5.8))

    ax.axvspan(TREATMENT_DATE, POST_END + pd.Timedelta(days=1), color="#f3f4f6", alpha=0.9, zorder=0)
    ax.axvline(TREATMENT_DATE, color="#9b2c2c", linewidth=1.4, linestyle=":")

    for group in ("Pooled controls", "NYC"):
        sub = daily[daily["group"] == group]
        ax.plot(
            sub["date"],
            sub["mean_ebike_per_station_hour"],
            color=colors[group],
            linewidth=2.4 if group == "NYC" else 2.1,
            label=group,
        )
        end = sub.iloc[-1]
        ax.annotate(
            group,
            xy=(end["date"], end["mean_ebike_per_station_hour"]),
            xytext=(8, 0),
            textcoords="offset points",
            color=colors[group],
            fontsize=10,
            fontweight="bold" if group == "NYC" else "normal",
            va="center",
        )

    ax.text(
        TREATMENT_DATE + pd.Timedelta(days=0.5),
        ax.get_ylim()[1],
        " Oct 24 policy date",
        color="#7a2c2c",
        ha="left",
        va="top",
        fontsize=9,
    )

    ax.set_title("Daily E-Bike Ridership per Station-Hour", fontsize=14, fontweight="bold", loc="left")
    ax.set_ylabel("E-bike trips per station-hour")
    ax.set_xlabel("")
    ax.set_xlim(PRE_START - pd.Timedelta(days=1), POST_END + pd.Timedelta(days=5))
    ax.xaxis.set_major_locator(WeekdayLocator(byweekday=0, interval=2))
    ax.xaxis.set_major_formatter(DateFormatter("%b %d"))
    ax.grid(axis="y", color="#d9dee7", linewidth=0.8)
    ax.grid(axis="x", visible=False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#9aa4b2")
    ax.spines["bottom"].set_color("#9aa4b2")
    ax.tick_params(colors="#374151")

    # Direct labels make the two-line comparison easier to read than a legend.
    legend = ax.get_legend()
    if legend is not None:
        legend.remove()

    fig.tight_layout()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(PNG_OUT, dpi=240, bbox_inches="tight")
    fig.savefig(PDF_OUT, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    daily = load_daily_average()
    daily.to_csv(DATA_OUT, index=False)
    plot_daily_average(daily)
    print(f"Wrote {DATA_OUT}")
    print(f"Wrote {PNG_OUT}")
    print(f"Wrote {PDF_OUT}")


if __name__ == "__main__":
    main()
