"""
Create paper-facing result tables in the figures directory.

The tables are derived from the CSV outputs in results/. Each table is written
as CSV, Markdown, LaTeX, PNG, and PDF so we can iterate on both content and
presentation.
"""

from __future__ import annotations

import os
import shutil
import textwrap
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLCONFIGDIR", str(PROJECT_ROOT / ".matplotlib_cache"))

import matplotlib.pyplot as plt  # noqa: E402


FIGURES_DIR = PROJECT_ROOT / "figures"
TABLES_DIR = FIGURES_DIR / "tables"
ROLLING_FIGURES_DIR = FIGURES_DIR / "rolling_att"
RESULTS_DIR = PROJECT_ROOT / "results"


def read_row(path: str | Path) -> pd.Series:
    """Read the row-weighted result when both row/station estimates are present."""

    df = pd.read_csv(PROJECT_ROOT / path)
    if "target" in df.columns:
        target = df[df["target"].astype(str).eq("row_weighted")]
        if not target.empty:
            return target.iloc[0]
    if "estimand" in df.columns:
        row = df[df["estimand"].astype(str).str.contains("row-weighted", regex=False)]
        if not row.empty:
            return row.iloc[0]
    return df.iloc[0]


def fmt_num(value: object, digits: int = 3) -> str:
    if pd.isna(value):
        return ""
    return f"{float(value):.{digits}f}"


def fmt_pct(value: object, digits: int = 1) -> str:
    if pd.isna(value):
        return ""
    return f"{100 * float(value):.{digits}f}%"


def fmt_int(value: object) -> str:
    if pd.isna(value):
        return ""
    return f"{int(value):,}"


def fmt_ci(row: pd.Series, low: str = "ci_low", high: str = "ci_high") -> str:
    return f"[{fmt_num(row[low])}, {fmt_num(row[high])}]"


def city_label(value: object) -> str:
    labels = {
        "boston": "Boston",
        "chicago": "Chicago",
        "philadelphia": "Philadelphia",
        "washington_dc": "Washington DC",
        "nyc": "NYC",
    }
    return labels.get(str(value), str(value).replace("_", " ").title())


def fmt_boot_ci(row: pd.Series) -> str:
    if "bootstrap_ci_low" not in row or pd.isna(row.get("bootstrap_ci_low")):
        return ""
    return f"[{fmt_num(row['bootstrap_ci_low'])}, {fmt_num(row['bootstrap_ci_high'])}]"


def window_label(row: pd.Series) -> str:
    t0_start = pd.Timestamp(row["t0_start"]).strftime("%b %d")
    t0_end = pd.Timestamp(row["t0_end"]).strftime("%b %d")
    t1_start = pd.Timestamp(row["t1_start"]).strftime("%b %d")
    t1_end = pd.Timestamp(row["t1_end"]).strftime("%b %d")
    year = pd.Timestamp(row["t1_start"]).year
    return f"{t0_start}-{t0_end} vs {t1_start}-{t1_end} {year}"


def result_row(
    label: str,
    path: str,
    outcome: str,
    unit: str,
    note: str = "",
    bootstrap_path: str | None = None,
) -> dict[str, object]:
    row = read_row(path)
    boot = read_row(bootstrap_path) if bootstrap_path else None
    return {
        "Specification": label,
        "Window": window_label(row),
        "Outcome": outcome,
        "Unit": unit,
        "ATT": fmt_num(row["att"]),
        "Analytic SE": fmt_num(row["standard_error"]),
        "Analytic 95% CI": fmt_ci(row),
        "Bootstrap 95% CI": fmt_boot_ci(boot) if boot is not None else "",
        "Rows": fmt_int(row.get("n_rows")),
        "Treated stations/units": fmt_int(row.get("n_treated_stations", row.get("n_treated_cities"))),
        "Control stations/units": fmt_int(row.get("n_control_stations", row.get("n_control_cities"))),
        "Trim share": fmt_pct(row.get("trimmed_share_if_dropped")),
        "Note": note,
    }


TABLE_NOTES = {
    "table_1_key_estimates": (
        "Sharp window: pre-treatment September 26-October 23, 2025; "
        "post-treatment October 24-November 20, 2025. Estimates use weather and time controls, "
        "without baseline-demand controls."
    ),
    "table_2_control_sensitivity": (
        "October 24 treatment sharp window: pre-treatment September 26-October 23, 2025; "
        "post-treatment October 24-November 20, 2025. Estimates use weather and time controls."
    ),
    "table_3_placebo_diagnostics": (
        "September-November specifications use September 1-21, 2025 "
        "versus November 3-23, 2025; "
        "all rows report row-weighted AIPTW estimates, without baseline-demand controls."
    ),
    "table_4_rolling_att": (
        "October 24 treatment rolling placebo-style estimates. Each assumed date uses four-week pre/post windows; "
        "estimates use weather and time controls."
    ),
    "table_5_sharp_window_diagnostics": (
        "Unless otherwise noted, sharp window uses pre-treatment September 26-October 23, 2025 "
        "and post-treatment October 24-November 20, 2025. Estimates use weather and time controls, "
        "without baseline-demand controls."
    ),
    "table_6_oct24_baseline_demand_controls": (
        "Window: September 26-October 23, 2025 vs October 24-November 20, 2025. "
        "Estimates use weather and time controls plus leave-one-out station-hour baseline e-bike demand."
    ),
    "table_7_june20_baseline_demand_controls": (
        "Window: May 23-June 19, 2025 vs June 20-July 17, 2025. "
        "Chicago is excluded because the June 2025 Divvy station ID change creates false early-window zeros. "
        "Estimates use weather and time controls plus leave-one-out station-hour baseline e-bike demand."
    ),
    "table_8_june20_no_baseline_controls": (
        "Window: May 23-June 19, 2025 vs June 20-July 17, 2025. "
        "Chicago is excluded because the June 2025 Divvy station ID change creates false early-window zeros. "
        "Estimates use weather and time controls, without baseline-demand controls."
    ),
    "table_9_june20_speed_threshold_bootstrap": (
        "Window: May 23-June 19, 2025 vs June 20-July 17, 2025. "
        "Outcome is post-minus-pre change in average straight-line speed in mph. "
        "Treatment is Citi Bike e-bikes; control is Citi Bike classic bikes. "
        "Bootstrap CIs resample OD-pair clusters with fixed nuisance predictions."
    ),
}


def render_markdown(df: pd.DataFrame, title: str, note: str = "") -> str:
    lines = [f"# {title}", ""]
    if note:
        lines.extend([f"*Note: {note}*", ""])
    cols = list(df.columns)
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("| " + " | ".join("---" for _ in cols) + " |")
    for _, row in df.iterrows():
        values = [str(row[col]).replace("\n", " ") for col in cols]
        lines.append("| " + " | ".join(values) + " |")
    lines.append("")
    return "\n".join(lines)


def render_table_image(df: pd.DataFrame, title: str, stem: str, font_size: int = 8, note: str = "") -> None:
    """Render a dataframe as a readable PNG/PDF table.

    Matplotlib tables do not automatically wrap text, so pre-wrap every cell
    and give rows enough height for the longest wrapped cell in that row.
    """

    wrap_widths = {
        "Specification": 22,
        "Window": 18,
        "Outcome": 14,
        "Unit": 12,
        "Analytic 95% CI": 16,
        "Bootstrap 95% CI": 16,
        "Note": 24,
        "Panel": 20,
        "Controls": 22,
        "Control set": 22,
        "Sensitivity": 18,
        "Diagnostic": 24,
        "Estimator detail": 18,
        "Post includes actual treatment time": 14,
    }
    default_width = 14
    display = df.copy()
    line_counts: list[int] = []
    for idx, row in display.iterrows():
        max_lines = 1
        for col in display.columns:
            width = wrap_widths.get(col, default_width)
            text = str(row[col])
            paragraphs = text.split("\n")
            wrapped_parts = [
                "\n".join(textwrap.wrap(part, width=width, break_long_words=False)) or part
                for part in paragraphs
            ]
            wrapped = "\n".join(wrapped_parts) or text
            display.at[idx, col] = wrapped
            max_lines = max(max_lines, wrapped.count("\n") + 1)
        line_counts.append(max_lines)

    wrapped_headers = []
    for col in display.columns:
        width = wrap_widths.get(col, default_width)
        wrapped_headers.append("\n".join(textwrap.wrap(str(col), width=max(8, width), break_long_words=False)))

    n_rows, n_cols = display.shape
    fig_width = min(max(12, n_cols * 1.45), 26)
    wrapped_note = "\n".join(textwrap.wrap(note, width=92, break_long_words=False)) if note else ""
    note_lines = wrapped_note.count("\n") + 1 if wrapped_note else 0
    note_space = 0.22 * note_lines if note else 0.0
    fig_height = max(2.6, 1.45 + note_space + sum(0.34 * count + 0.20 for count in line_counts))
    fig, ax = plt.subplots(figsize=(fig_width, fig_height))
    ax.axis("off")
    wrapped_title = "\n".join(textwrap.wrap(title, width=48, break_long_words=False))
    ax.set_title(wrapped_title, fontsize=15, fontweight="bold", pad=4, linespacing=1.18)
    if note:
        ax.text(
            0.5,
            0.955,
            wrapped_note,
            transform=ax.transAxes,
            ha="center",
            va="top",
            fontsize=9,
            color="#334e68",
            linespacing=1.15,
        )

    table = ax.table(
        cellText=display.values,
        colLabels=wrapped_headers,
        cellLoc="center",
        colLoc="center",
        loc="center",
        bbox=[0, 0, 1, max(0.76, 0.92 - 0.045 * note_lines) if note else 0.96],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)
    table.scale(1, 1.0)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#c7c7c7")
        if row == 0:
            cell.set_facecolor("#243b53")
            cell.set_text_props(color="white", weight="bold")
            cell.set_height(0.08)
        elif row % 2 == 0:
            cell.set_facecolor("#f4f6f8")
            cell.set_height(0.055 * line_counts[row - 1])
        else:
            cell.set_facecolor("white")
            cell.set_height(0.055 * line_counts[row - 1])
        if row > 0 and display.columns[col] in {
            "Panel",
            "Specification",
            "Note",
            "Controls",
            "Control set",
            "Sensitivity",
            "Diagnostic",
            "Estimator detail",
        }:
            cell.set_text_props(ha="left")
    fig.tight_layout(pad=0.6)
    table_dir = TABLES_DIR / stem
    table_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(table_dir / f"{stem}.png", dpi=250, bbox_inches="tight")
    fig.savefig(table_dir / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def write_table(df: pd.DataFrame, title: str, stem: str, font_size: int = 8) -> None:
    table_dir = TABLES_DIR / stem
    table_dir.mkdir(parents=True, exist_ok=True)
    note = TABLE_NOTES.get(stem, "")
    df.to_csv(table_dir / f"{stem}.csv", index=False)
    (table_dir / f"{stem}.md").write_text(render_markdown(df, title, note=note))
    df.to_latex(table_dir / f"{stem}.tex", index=False, escape=True)
    render_table_image(df, title, stem, font_size=font_size, note=note)


def make_key_estimates_table() -> pd.DataFrame:
    """Make the main sharp-window table plus control-group sensitivities.

    The table keeps the preferred pooled-control estimate and the same-window
    individual-control and leave-one-control-out checks together, so the main
    specification is not isolated from the most directly related sensitivities.
    """

    rows: list[dict[str, object]] = []
    main = read_row("results/sensitivities/sharp_window_time_controls_summary.csv")
    main_boot = read_row("results/main_spec/sharp_window_bootstrap_summary.csv")
    rows.append(
        {
            "Panel": "Main",
            "Specification": "Pooled",
            "Controls": "All four control cities",
            "ATT": fmt_num(main["att"]),
            "SE": fmt_num(main["standard_error"]),
            "95% CI": f"{fmt_ci(main)} analytic\n\n{fmt_boot_ci(main_boot)} bootstrap",
        }
    )
    trimmed = read_row("results/sensitivities/sharp_window_trimmed_summary.csv")
    rows.append(
        {
            "Panel": "Robustness",
            "Specification": "Propensity trimming",
            "Controls": "All four control cities",
            "ATT": fmt_num(trimmed["att"]),
            "SE": fmt_num(trimmed["standard_error"]),
            "95% CI": fmt_ci(trimmed),
        }
    )

    one = pd.read_csv(PROJECT_ROOT / "results/sensitivities/sharp_one_control_city_summary.csv")
    one = one[one["estimand"].str.contains("row-weighted", regex=False)].copy()
    city_order = ["chicago", "boston", "philadelphia", "washington_dc"]
    one["order"] = one["control_city"].map({city: idx for idx, city in enumerate(city_order)})
    one = one.sort_values("order")
    for _, row in one.iterrows():
        city = city_label(row["control_city"])
        rows.append(
            {
                "Panel": "Individual controls",
                "Specification": f"NYC vs {city}",
                "Controls": city,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )

    loo = pd.read_csv(PROJECT_ROOT / "results/sensitivities/sharp_leave_one_control_out_summary.csv")
    loo = loo[loo["estimand"].str.contains("row-weighted", regex=False)].copy()
    loo["order"] = loo["omitted_control_city"].map({city: idx for idx, city in enumerate(city_order)})
    loo = loo.sort_values("order")
    for _, row in loo.iterrows():
        omitted = city_label(row["omitted_control_city"])
        controls = ", ".join(city_label(city) for city in str(row["control_cities"]).split(","))
        rows.append(
            {
                "Panel": "Leave-one-out",
                "Specification": f"Excluding {omitted}",
                "Controls": controls,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )

    return pd.DataFrame(rows)


def make_baseline_demand_control_group_table(
    *,
    pooled_path: str,
    bootstrap_path: str,
    one_control_path: str,
    leave_one_out_path: str,
    pooled_controls_label: str = "All four control cities",
    city_order: list[str] | None = None,
) -> pd.DataFrame:
    """Make a Table-1-style result table for baseline-demand specifications."""

    city_order = city_order or ["chicago", "boston", "philadelphia", "washington_dc"]
    rows: list[dict[str, object]] = []
    pooled = read_row(pooled_path)
    pooled_boot = read_row(bootstrap_path)
    rows.append(
        {
            "Panel": "Main",
            "Specification": "Pooled",
            "Controls": pooled_controls_label,
            "ATT": fmt_num(pooled["att"]),
            "SE": fmt_num(pooled["standard_error"]),
            "95% CI": f"{fmt_ci(pooled)} analytic\n\n{fmt_boot_ci(pooled_boot)} bootstrap",
        }
    )

    one = pd.read_csv(PROJECT_ROOT / one_control_path)
    one = one[one["estimand"].str.contains("row-weighted", regex=False)].copy()
    one["order"] = one["control_city"].map({city: idx for idx, city in enumerate(city_order)})
    one = one.sort_values("order")
    for _, row in one.iterrows():
        city = city_label(row["control_city"])
        rows.append(
            {
                "Panel": "Individual controls",
                "Specification": f"NYC vs {city}",
                "Controls": city,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )

    loo = pd.read_csv(PROJECT_ROOT / leave_one_out_path)
    loo = loo[loo["estimand"].str.contains("row-weighted", regex=False)].copy()
    loo["order"] = loo["omitted_control_city"].map({city: idx for idx, city in enumerate(city_order)})
    loo = loo.sort_values("order")
    for _, row in loo.iterrows():
        omitted = city_label(row["omitted_control_city"])
        controls = ", ".join(city_label(city) for city in str(row["control_cities"]).split(","))
        rows.append(
            {
                "Panel": "Leave-one-out",
                "Specification": f"Excluding {omitted}",
                "Controls": controls,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )

    return pd.DataFrame(rows)


def make_oct24_baseline_demand_table() -> pd.DataFrame:
    return make_baseline_demand_control_group_table(
        pooled_path="results/sensitivities/sharp_window_baseline_demand_controls_summary.csv",
        bootstrap_path="results/main_spec/sharp_window_baseline_demand_bootstrap_summary.csv",
        one_control_path="results/sensitivities/sharp_window_baseline_demand_one_control_city_summary.csv",
        leave_one_out_path="results/sensitivities/sharp_window_baseline_demand_leave_one_control_out_summary.csv",
    )


def make_june20_baseline_demand_table() -> pd.DataFrame:
    return make_baseline_demand_control_group_table(
        pooled_path="results/june_20_no_chicago/june_20_baseline_demand_no_chicago_pooled_summary.csv",
        bootstrap_path="results/june_20_no_chicago/june_20_baseline_demand_no_chicago_bootstrap_summary.csv",
        one_control_path="results/june_20_no_chicago/june_20_baseline_demand_no_chicago_one_control_city_summary.csv",
        leave_one_out_path="results/june_20_no_chicago/june_20_baseline_demand_no_chicago_leave_one_control_out_summary.csv",
        pooled_controls_label="Boston, Philadelphia, Washington DC",
        city_order=["boston", "philadelphia", "washington_dc"],
    )


def make_june20_no_baseline_table() -> pd.DataFrame:
    return make_baseline_demand_control_group_table(
        pooled_path="results/june_20_no_chicago/june_20_no_chicago_pooled_summary.csv",
        bootstrap_path="results/june_20_no_chicago/june_20_no_chicago_bootstrap_summary.csv",
        one_control_path="results/june_20_no_chicago/june_20_no_chicago_one_control_city_summary.csv",
        leave_one_out_path="results/june_20_no_chicago/june_20_no_chicago_leave_one_control_out_summary.csv",
        pooled_controls_label="Boston, Philadelphia, Washington DC",
        city_order=["boston", "philadelphia", "washington_dc"],
    )


def make_june20_speed_threshold_bootstrap_table() -> pd.DataFrame:
    """Make a compact table for the June 20 speed threshold sensitivities."""

    df = pd.read_csv(PROJECT_ROOT / "results/speed/02_june20_speed_threshold_bootstrap_summary.csv")
    df = df.sort_values("threshold_min_total_rides_per_type")
    rows = []
    for _, row in df.iterrows():
        rows.append(
            {
                "Min rides per OD/type": fmt_int(row["threshold_min_total_rides_per_type"]),
                "OD pairs": fmt_int(row["n_od_pair_clusters"]),
                "Rows": fmt_int(row["n_rows"]),
                "ATT mph": fmt_num(row["att"]),
                "Analytic SE": fmt_num(row["standard_error"]),
                "Analytic 95% CI": fmt_ci(row),
                "Bootstrap SE": fmt_num(row["bootstrap_standard_error"]),
                "Bootstrap 95% CI": fmt_boot_ci(row),
            }
        )
    return pd.DataFrame(rows)


def make_control_sensitivity_table() -> pd.DataFrame:
    pieces = []
    one = pd.read_csv(PROJECT_ROOT / "results/sensitivities/sharp_one_control_city_summary.csv")
    one = one[one["estimand"].str.contains("row-weighted", regex=False)].copy()
    for _, row in one.iterrows():
        pieces.append(
            {
                "Sensitivity": "NYC vs one control",
                "Control set": str(row["control_city"]).replace("_", " ").title(),
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
                "Rows": fmt_int(row["n_rows"]),
                "Control stations": fmt_int(row["n_control_stations"]),
                "Trim share": fmt_pct(row["trimmed_share_if_dropped"]),
            }
        )

    loo = pd.read_csv(PROJECT_ROOT / "results/sensitivities/sharp_leave_one_control_out_summary.csv")
    loo = loo[loo["estimand"].str.contains("row-weighted", regex=False)].copy()
    for _, row in loo.iterrows():
        pieces.append(
            {
                "Sensitivity": "Leave one control out",
                "Control set": f"All except {str(row['omitted_control_city']).replace('_', ' ').title()}",
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
                "Rows": fmt_int(row["n_rows"]),
                "Control stations": fmt_int(row["n_control_stations"]),
                "Trim share": fmt_pct(row["trimmed_share_if_dropped"]),
            }
        )
    return pd.DataFrame(pieces)


def make_sharp_window_diagnostics_table() -> pd.DataFrame:
    """Make a compact table for non-control-group sharp-window diagnostics."""

    specs = [
        (
            "2024 placebo",
            "Same calendar window in 2024",
            "E-bike trips",
            "Station-hour",
            "results/sensitivities/sharp_2024_placebo_time_controls_summary.csv",
        ),
        (
            "Classic rides",
            "Same design with classic rides as outcome",
            "Classic trips",
            "Station-hour",
            "results/sensitivities/sharp_classic_rides_robustness_summary.csv",
        ),
        (
            "Ride composition",
            "City-hour e-bike trips / total trips",
            "E-bike share",
            "City-hour",
            "results/sensitivities/sharp_ebike_share_city_hour_aiptw_summary.csv",
        ),
    ]
    rows = []
    for diagnostic, detail, outcome, unit, path in specs:
        row = read_row(path)
        rows.append(
            {
                "Diagnostic": diagnostic,
                "Estimator detail": detail,
                "Outcome": outcome,
                "Unit": unit,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )
    return pd.DataFrame(rows)


def make_diagnostics_table() -> pd.DataFrame:
    specs = [
        ("September-November window", "Weather controls", "E-bike trips", "results/01_aiptw_att_row_weighted.csv"),
        (
            "September-November window",
            "Weather and time controls",
            "E-bike trips",
            "results/sensitivities/main_time_controls_summary.csv",
        ),
        (
            "September-November window",
            "Weather and daylight controls",
            "E-bike trips",
            "results/sensitivities/main_daylight_controls_summary.csv",
        ),
        (
            "September-November window",
            "Weather controls",
            "Classic trips",
            "results/sensitivities/classic_rides_robustness_summary.csv",
        ),
    ]
    rows = []
    for specification, covariates, outcome, path in specs:
        row = read_row(path)
        rows.append(
            {
                "Specification": specification,
                "Covariates": covariates,
                "Outcome": outcome,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
            }
        )
    return pd.DataFrame(rows)


def make_rolling_table() -> pd.DataFrame:
    df = pd.read_csv(PROJECT_ROOT / "results/rolling_att/rolling_att_summary.csv")
    rows = []
    for _, row in df.iterrows():
        assumed = pd.Timestamp(row["assumed_treatment_date"])
        overlaps = "Yes" if assumed >= pd.Timestamp("2025-10-03") else "No"
        rows.append(
            {
                "Assumed date": assumed.strftime("%Y-%m-%d"),
                "Post includes actual treatment time": overlaps,
                "ATT": fmt_num(row["att"]),
                "SE": fmt_num(row["standard_error"]),
                "95% CI": fmt_ci(row),
                "Rows": fmt_int(row["n_rows"]),
                "Treated stations": fmt_int(row["n_treated_stations"]),
                "Control stations": fmt_int(row["n_control_stations"]),
                "Trim share": fmt_pct(row["trimmed_share_if_dropped"]),
            }
        )
    return pd.DataFrame(rows)


def copy_existing_figures() -> None:
    ROLLING_FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf"):
        src = PROJECT_ROOT / "results" / "rolling_att" / "figures" / f"rolling_att_plot.{suffix}"
        if src.exists():
            shutil.copy2(src, ROLLING_FIGURES_DIR / f"figure_rolling_att_plot.{suffix}")


def main() -> None:
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    tables = [
        ("October 24 Treatment, No Baseline-Demand Controls Sharp-Window AIPTW ATT by Control Group", "table_1_key_estimates", make_key_estimates_table(), 11),
        ("Control-Group Sensitivity", "table_2_control_sensitivity", make_control_sensitivity_table(), 8),
        ("October 24 Treatment September-November Sensitivity Specifications", "table_3_placebo_diagnostics", make_diagnostics_table(), 10),
        ("Rolling Assumed-Treatment-Date Estimates", "table_4_rolling_att", make_rolling_table(), 8),
        ("October 24 Treatment Sharp-Window Diagnostic Specifications", "table_5_sharp_window_diagnostics", make_sharp_window_diagnostics_table(), 9),
        (
            "October 24 Baseline-Demand AIPTW ATT by Control Group",
            "table_6_oct24_baseline_demand_controls",
            make_oct24_baseline_demand_table(),
            11,
        ),
        (
            "June 20 Baseline-Demand AIPTW ATT by Control Group",
            "table_7_june20_baseline_demand_controls",
            make_june20_baseline_demand_table(),
            11,
        ),
        (
            "June 20 Treatment, No Baseline-Demand Controls AIPTW ATT by Control Group",
            "table_8_june20_no_baseline_controls",
            make_june20_no_baseline_table(),
            11,
        ),
        (
            "June 20 E-Bike Speed Threshold Sensitivities",
            "table_9_june20_speed_threshold_bootstrap",
            make_june20_speed_threshold_bootstrap_table(),
            10,
        ),
    ]
    for title, stem, df, font_size in tables:
        write_table(df, title, stem, font_size=font_size)
        print(f"Wrote figures/tables/{stem}.[csv,md,tex,png,pdf]")
    copy_existing_figures()
    print("Copied rolling ATT plot to figures/rolling_att/figure_rolling_att_plot.[png,pdf]")


if __name__ == "__main__":
    main()
