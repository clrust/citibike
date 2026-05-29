"""
Create descriptive ridership plots for visual inspection.

These figures are not causal estimates. They aggregate the cleaned rolling
station-hour panel to city-hour and city-day ridership so we can eyeball NYC
against the control systems, both individually and pooled.
"""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.dates import DateFormatter, MonthLocator, WeekdayLocator  # noqa: E402


INPUT_PATH = PROJECT_ROOT / "data_clean" / "rolling_att" / "01_rolling_station_hour_panel_weather.csv"
JUNE20_INPUT_PATH = PROJECT_ROOT / "data_clean" / "june_20" / "01_june_20_station_hour_panel_weather.csv"
FIGURES_DIR = PROJECT_ROOT / "figures"
DESCRIPTIVE_DIR = FIGURES_DIR / "descriptive_ridership"
DESCRIPTIVE_DATA_DIR = DESCRIPTIVE_DIR / "data"
DAY_FIGURE_DIR = DESCRIPTIVE_DIR / "day_level"
HOUR_FIGURE_DIR = DESCRIPTIVE_DIR / "hour_level"
DAILY_OUT = DESCRIPTIVE_DATA_DIR / "descriptive_city_day_ridership.csv"
HOURLY_OUT = DESCRIPTIVE_DATA_DIR / "descriptive_city_hour_ridership.csv"
JUNE20_DAILY_OUT = DESCRIPTIVE_DATA_DIR / "descriptive_city_day_ridership_june20.csv"

CONTROL_CITIES = ("chicago", "boston", "philadelphia", "washington_dc")
CITY_LABELS = {
    "nyc": "NYC",
    "chicago": "Chicago",
    "boston": "Boston",
    "philadelphia": "Philadelphia",
    "washington_dc": "Washington DC",
    "pooled_controls": "Pooled controls",
}
CITY_COLORS = {
    "nyc": "#1f4e79",
    "chicago": "#c76f2a",
    "boston": "#4c956c",
    "philadelphia": "#7b5ea7",
    "washington_dc": "#b23a48",
    "pooled_controls": "#5f6c7b",
}
OCT24 = pd.Timestamp("2025-10-24")
JUN20 = pd.Timestamp("2025-06-20")
PRE_START = pd.Timestamp("2025-09-26")
PRE_END = pd.Timestamp("2025-10-23")
JUNE20_PRE_START = pd.Timestamp("2025-05-23")
JUNE20_PRE_END = pd.Timestamp("2025-06-19")


def load_city_hour(input_path: Path = INPUT_PATH) -> pd.DataFrame:
    usecols = ["city", "station_hour", "ebike_trip_count", "classic_trip_count", "trip_count"]
    panel = pd.read_csv(input_path, usecols=usecols, parse_dates=["station_hour"], low_memory=False)
    city_hour = (
        panel.groupby(["city", "station_hour"], as_index=False)
        .agg(
            ebike_trips=("ebike_trip_count", "sum"),
            classic_trips=("classic_trip_count", "sum"),
            total_trips=("trip_count", "sum"),
        )
        .sort_values(["city", "station_hour"])
    )
    city_hour["date"] = city_hour["station_hour"].dt.normalize()
    return city_hour


def add_pooled_controls(frame: pd.DataFrame, time_col: str) -> pd.DataFrame:
    controls = (
        frame[frame["city"].isin(CONTROL_CITIES)]
        .groupby(time_col, as_index=False)
        .agg(
            ebike_trips=("ebike_trips", "sum"),
            classic_trips=("classic_trips", "sum"),
            total_trips=("total_trips", "sum"),
        )
    )
    controls["city"] = "pooled_controls"
    return pd.concat([frame, controls], ignore_index=True, sort=False)


def make_city_day(city_hour: pd.DataFrame) -> pd.DataFrame:
    city_day = (
        city_hour.groupby(["city", "date"], as_index=False)
        .agg(
            ebike_trips=("ebike_trips", "sum"),
            classic_trips=("classic_trips", "sum"),
            total_trips=("total_trips", "sum"),
        )
        .sort_values(["city", "date"])
    )
    city_day = add_pooled_controls(city_day, "date")
    city_day["ebike_share"] = city_day["ebike_trips"] / (city_day["ebike_trips"] + city_day["classic_trips"])
    for outcome in ("ebike_trips", "classic_trips", "total_trips", "ebike_share"):
        city_day[f"{outcome}_roll7"] = city_day.groupby("city")[outcome].transform(
            lambda s: s.rolling(7, min_periods=3).mean()
        )
    return city_day.sort_values(["city", "date"]).reset_index(drop=True)


def make_city_hour_for_plot(city_hour: pd.DataFrame) -> pd.DataFrame:
    city_hour = add_pooled_controls(city_hour, "station_hour")
    for outcome in ("ebike_trips", "classic_trips", "total_trips"):
        city_hour[f"{outcome}_roll24"] = city_hour.groupby("city")[outcome].transform(
            lambda s: s.rolling(24, min_periods=12).mean()
        )
    return city_hour.sort_values(["city", "station_hour"]).reset_index(drop=True)


def add_indexed_columns(
    frame: pd.DataFrame,
    time_col: str,
    outcomes: tuple[str, ...],
    pre_start: pd.Timestamp = PRE_START,
    pre_end: pd.Timestamp = PRE_END,
) -> pd.DataFrame:
    out = frame.copy()
    pre_mask = out[time_col].between(pre_start, pre_end)
    for outcome in outcomes:
        baseline = out.loc[pre_mask].groupby("city")[outcome].mean()
        out[f"{outcome}_index"] = out[outcome] / out["city"].map(baseline) * 100
    return out


def format_time_axis(ax, weekly: bool = False, event_date: pd.Timestamp = OCT24, event_label: str = "Oct 24") -> None:
    ax.axvline(event_date, color="#9b2c2c", linewidth=1.4, linestyle=":", label=event_label)
    if weekly:
        ax.xaxis.set_major_locator(WeekdayLocator(byweekday=0, interval=2))
    else:
        ax.xaxis.set_major_locator(MonthLocator())
    ax.xaxis.set_major_formatter(DateFormatter("%b %d"))
    ax.grid(axis="y", color="#dddddd", linewidth=0.8)


def save_fig(fig, stem: str, out_dir: Path) -> None:
    fig.tight_layout()
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(out_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_daily_city_panels(
    city_day: pd.DataFrame,
    outcome: str,
    title: str,
    ylabel: str,
    stem: str,
    cities: tuple[str, ...] = ("nyc", "chicago", "boston", "philadelphia", "washington_dc"),
    event_date: pd.Timestamp = OCT24,
    event_label: str = "Oct 24",
) -> None:
    fig, axes = plt.subplots(len(cities), 1, figsize=(11, 9), sharex=True)
    for ax, city in zip(axes, cities, strict=True):
        sub = city_day[city_day["city"] == city]
        ax.plot(sub["date"], sub[outcome], color=BODY_COLOR, alpha=0.20, linewidth=0.8)
        ax.plot(sub["date"], sub[f"{outcome}_roll7"], color=CITY_COLORS[city], linewidth=2)
        ax.text(0.01, 0.84, CITY_LABELS[city], transform=ax.transAxes, fontsize=10, fontweight="bold")
        format_time_axis(ax, weekly=True, event_date=event_date, event_label=event_label)
        ax.set_ylabel(ylabel)
    axes[0].set_title(title)
    axes[-1].set_xlabel("Date")
    save_fig(fig, stem, DAY_FIGURE_DIR)


def plot_nyc_vs_controls_daily_index(city_day: pd.DataFrame) -> None:
    work = add_indexed_columns(city_day, "date", ("ebike_trips_roll7", "classic_trips_roll7"))
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    specs = [
        ("ebike_trips_roll7_index", "E-bike trips, indexed to Sep 26-Oct 23 average"),
        ("classic_trips_roll7_index", "Classic trips, indexed to Sep 26-Oct 23 average"),
    ]
    for ax, (col, title) in zip(axes, specs, strict=True):
        for city in ("pooled_controls", "nyc"):
            sub = work[work["city"] == city]
            ax.plot(sub["date"], sub[col], color=CITY_COLORS[city], linewidth=2.2, label=CITY_LABELS[city])
        ax.axhline(100, color="#555555", linewidth=1, linestyle="--")
        format_time_axis(ax, weekly=True)
        ax.set_title(title)
        ax.set_ylabel("Index")
        ax.legend(loc="best", frameon=False)
    axes[-1].set_xlabel("Date")
    save_fig(fig, "descriptive_daily_index_nyc_vs_pooled_controls", DAY_FIGURE_DIR)


def plot_individual_controls_daily_index(
    city_day: pd.DataFrame,
    outcome: str,
    title: str,
    stem: str,
    control_cities: tuple[str, ...] = CONTROL_CITIES,
    pre_start: pd.Timestamp = PRE_START,
    pre_end: pd.Timestamp = PRE_END,
    event_date: pd.Timestamp = OCT24,
    event_label: str = "Oct 24",
) -> None:
    work = add_indexed_columns(city_day, "date", (f"{outcome}_roll7",), pre_start=pre_start, pre_end=pre_end)
    col = f"{outcome}_roll7_index"
    fig, ax = plt.subplots(figsize=(11, 5.8))
    for city in control_cities:
        sub = work[work["city"] == city]
        ax.plot(sub["date"], sub[col], color=CITY_COLORS[city], linewidth=1.8, alpha=0.80, label=CITY_LABELS[city])
    sub = work[work["city"] == "nyc"]
    ax.plot(sub["date"], sub[col], color=CITY_COLORS["nyc"], linewidth=2.8, label="NYC")
    ax.axhline(100, color="#555555", linewidth=1, linestyle="--")
    format_time_axis(ax, weekly=True, event_date=event_date, event_label=event_label)
    ax.set_title(title)
    ax.set_ylabel("Index")
    ax.set_xlabel("Date")
    ax.legend(ncol=3, frameon=False)
    save_fig(fig, stem, DAY_FIGURE_DIR)


def plot_hourly_nyc_vs_controls(city_hour: pd.DataFrame) -> None:
    work = add_indexed_columns(city_hour, "station_hour", ("ebike_trips_roll24", "classic_trips_roll24"))
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    specs = [
        ("ebike_trips_roll24_index", "Hourly e-bike trips, 24-hour rolling mean index"),
        ("classic_trips_roll24_index", "Hourly classic trips, 24-hour rolling mean index"),
    ]
    for ax, (col, title) in zip(axes, specs, strict=True):
        for city in ("pooled_controls", "nyc"):
            sub = work[work["city"] == city]
            ax.plot(sub["station_hour"], sub[col], color=CITY_COLORS[city], linewidth=1.6, label=CITY_LABELS[city])
        ax.axhline(100, color="#555555", linewidth=1, linestyle="--")
        format_time_axis(ax, weekly=False)
        ax.set_title(title)
        ax.set_ylabel("Index")
        ax.legend(loc="best", frameon=False)
    axes[-1].set_xlabel("Date")
    save_fig(fig, "descriptive_hourly_index_nyc_vs_pooled_controls", HOUR_FIGURE_DIR)


def plot_ebike_share(city_day: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(11, 5.5))
    for city in ("pooled_controls", "nyc"):
        sub = city_day[city_day["city"] == city]
        ax.plot(sub["date"], sub["ebike_share_roll7"] * 100, color=CITY_COLORS[city], linewidth=2.4, label=CITY_LABELS[city])
    format_time_axis(ax, weekly=True)
    ax.set_title("Daily e-bike share, NYC vs pooled controls")
    ax.set_ylabel("E-bike share of classic + e-bike trips (%)")
    ax.set_xlabel("Date")
    ax.legend(frameon=False)
    save_fig(fig, "descriptive_daily_ebike_share_nyc_vs_pooled_controls", DAY_FIGURE_DIR)


BODY_COLOR = "#1d2733"


def main() -> None:
    DESCRIPTIVE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    DAY_FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    HOUR_FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    city_hour_raw = load_city_hour()
    city_day = make_city_day(city_hour_raw)
    city_hour = make_city_hour_for_plot(city_hour_raw)

    city_day.to_csv(DAILY_OUT, index=False)
    city_hour.to_csv(HOURLY_OUT, index=False)

    plot_daily_city_panels(
        city_day,
        "ebike_trips",
        "Daily e-bike trips by city",
        "Trips",
        "descriptive_daily_ebike_trips_by_city",
    )
    plot_daily_city_panels(
        city_day,
        "classic_trips",
        "Daily classic-bike trips by city",
        "Trips",
        "descriptive_daily_classic_trips_by_city",
    )
    plot_nyc_vs_controls_daily_index(city_day)
    plot_individual_controls_daily_index(
        city_day,
        "ebike_trips",
        "Daily e-bike trips, indexed: NYC and individual controls",
        "descriptive_daily_ebike_index_nyc_vs_individual_controls",
    )
    plot_individual_controls_daily_index(
        city_day,
        "classic_trips",
        "Daily classic-bike trips, indexed: NYC and individual controls",
        "descriptive_daily_classic_index_nyc_vs_individual_controls",
    )
    plot_hourly_nyc_vs_controls(city_hour)
    plot_ebike_share(city_day)

    # June 20 analog of the individual-control e-bike index plot. This uses
    # the June 20 panel and indexes each city to its own May 23-June 19 average.
    june20_city_day = make_city_day(load_city_hour(JUNE20_INPUT_PATH))
    june20_city_day.to_csv(JUNE20_DAILY_OUT, index=False)
    plot_individual_controls_daily_index(
        june20_city_day,
        "ebike_trips",
        "Daily e-bike trips, indexed: NYC and individual controls, June 20 window",
        "descriptive_daily_ebike_index_nyc_vs_individual_controls_june20",
        pre_start=JUNE20_PRE_START,
        pre_end=JUNE20_PRE_END,
        event_date=JUN20,
        event_label="Jun 20",
    )
    plot_individual_controls_daily_index(
        june20_city_day,
        "ebike_trips",
        "Daily e-bike trips, indexed: NYC and controls, June 20 window, no Chicago",
        "descriptive_daily_ebike_index_nyc_vs_individual_controls_june20_no_chicago",
        control_cities=("boston", "philadelphia", "washington_dc"),
        pre_start=JUNE20_PRE_START,
        pre_end=JUNE20_PRE_END,
        event_date=JUN20,
        event_label="Jun 20",
    )
    plot_daily_city_panels(
        june20_city_day,
        "ebike_trips",
        "Daily e-bike trips by city, June 20 window, no Chicago",
        "Trips",
        "descriptive_daily_ebike_trips_by_city_june20_no_chicago",
        cities=("nyc", "boston", "philadelphia", "washington_dc"),
        event_date=JUN20,
        event_label="Jun 20",
    )

    print(f"Wrote daily aggregates to {DAILY_OUT}")
    print(f"Wrote hourly aggregates to {HOURLY_OUT}")
    print(f"Wrote June 20 daily aggregates to {JUNE20_DAILY_OUT}")
    print("Wrote descriptive ridership plots to figures/descriptive_ridership/")


if __name__ == "__main__":
    main()
