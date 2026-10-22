"""When does net-zero CO2 happen in IPCC AR6 scenarios? A small, reproducible example.

What this script does
---------------------
1. Loads global net CO2 emissions ("Emissions|CO2", region "World") for scenarios in the
   public IPCC AR6 Scenario Database hosted by IIASA, together with each scenario's
   temperature category (C1, C2, C3).
2. Finds, for every scenario, the year in which net CO2 emissions first reach zero
   (linear interpolation between model time steps).
3. Summarises the timing per category and draws two figures:
   - net CO2 pathways with the median per category
   - the spread of net-zero years per category

What it does NOT do
-------------------
It works with NET CO2 only. Gross emissions and residual emissions are not part of this
example (they cannot be calculated directly from the standard AR6 reporting variables).

Usage
-----
    python ar6_netzero.py          # real AR6 data (needs internet and the pyam package)
    python ar6_netzero.py --demo   # synthetic demo data, no internet needed

Demo outputs are clearly labelled as synthetic and must not be read as AR6 results.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

VARIABLE = "Emissions|CO2"  # net CO2, unit Mt CO2/yr in AR6
REGION = "World"
CATEGORIES = ["C1", "C2", "C3"]
CATEGORY_LABELS = {
    "C1": "C1: 1.5°C, no or limited overshoot",
    "C2": "C2: 1.5°C, high overshoot",
    "C3": "C3: 2°C, likely",
}
# Colour-blind-safe colours, one per category (used identically in both figures)
CATEGORY_COLOURS = {"C1": "#0072B2", "C2": "#E69F00", "C3": "#009E73"}


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------
def load_ar6() -> pd.DataFrame:
    """Download World net CO2 and the temperature category from the public AR6 database."""
    import pyam  # imported here so --demo works without pyam installed

    iam_df = pyam.read_iiasa("ar6-public", variable=VARIABLE, region=REGION, meta=True)
    long_df = iam_df.as_pandas(meta_cols=["Category"])
    return long_df.rename(columns={"Category": "category"})


def make_demo_data(seed: int = 42) -> pd.DataFrame:
    """Synthetic scenarios in the same long format. For testing and demonstration only."""
    rng = np.random.default_rng(seed)
    years = np.arange(2020, 2101, 10)
    # (typical net-zero year, number of scenarios) per category
    setup = {"C1": (2055, 12), "C2": (2062, 10), "C3": (2072, 14)}
    rows = []
    for cat, (zero_year, n) in setup.items():
        for i in range(n):
            start = 40000 + rng.normal(0, 1500)  # Mt CO2/yr
            zero = zero_year + rng.normal(0, 6)
            end = -rng.uniform(2000, 12000) if cat != "C3" else -rng.uniform(0, 5000)
            for y in years:
                if y <= zero:
                    value = start * (1 - (y - 2020) / (zero - 2020))
                else:
                    value = end * min(1.0, (y - zero) / (2100 - zero))
                rows.append(
                    {
                        "model": f"DemoModel {chr(65 + i % 3)}",
                        "scenario": f"{cat}-demo-{i}",
                        "year": int(y),
                        "value": float(value + rng.normal(0, 400)),
                        "category": f"{cat}: demo",
                    }
                )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------------------
# Analysis
# --------------------------------------------------------------------------------------
def prepare(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the columns we need, reduce category names to C1/C2/C3, convert Mt to Gt."""
    out = df[["model", "scenario", "year", "value", "category"]].copy()
    out["category"] = out["category"].astype(str).str.extract(r"^(C\d+)", expand=False)
    out = out.dropna(subset=["category", "value"])
    out = out[out["category"].isin(CATEGORIES)].copy()
    out["year"] = out["year"].astype(int)
    out["value_gt"] = out["value"] / 1000.0  # Mt CO2/yr -> Gt CO2/yr
    return out.reset_index(drop=True)


def crossing_year(years, values) -> float:
    """First year in which values reach zero or below, interpolated linearly.

    Returns NaN if the series never reaches zero. If the first value is already
    zero or below, the first year is returned.
    """
    years = np.asarray(years, dtype=float)
    values = np.asarray(values, dtype=float)
    order = np.argsort(years)
    years, values = years[order], values[order]

    hits = np.flatnonzero(values <= 0)
    if hits.size == 0:
        return float("nan")
    i = hits[0]
    if i == 0:
        return float(years[0])
    y0, y1 = years[i - 1], years[i]
    v0, v1 = values[i - 1], values[i]  # v0 > 0 >= v1, so the denominator is positive
    return float(y0 + (y1 - y0) * v0 / (v0 - v1))


def net_zero_years(df: pd.DataFrame) -> pd.DataFrame:
    """One row per scenario with the net-zero year (NaN if never reached)."""
    rows = []
    for (model, scenario, category), grp in df.groupby(["model", "scenario", "category"]):
        rows.append(
            {
                "model": model,
                "scenario": scenario,
                "category": category,
                "net_zero_year": crossing_year(grp["year"], grp["value_gt"]),
            }
        )
    return pd.DataFrame(rows)


def summarise(nz: pd.DataFrame) -> pd.DataFrame:
    """Per category: number of scenarios, how many reach net zero, median and quartiles."""
    rows = []
    for cat in CATEGORIES:
        sub = nz[nz["category"] == cat]
        reached = sub["net_zero_year"].dropna()
        rows.append(
            {
                "category": cat,
                "scenarios": len(sub),
                "reaching_net_zero": len(reached),
                "median_year": reached.median() if len(reached) else np.nan,
                "p25_year": reached.quantile(0.25) if len(reached) else np.nan,
                "p75_year": reached.quantile(0.75) if len(reached) else np.nan,
            }
        )
    return pd.DataFrame(rows).round(1)


# --------------------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------------------
def plot_pathways(df: pd.DataFrame, path: Path, note: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    for cat in CATEGORIES:
        sub = df[df["category"] == cat]
        colour = CATEGORY_COLOURS[cat]
        for _, grp in sub.groupby(["model", "scenario"]):
            grp = grp.sort_values("year")
            ax.plot(grp["year"], grp["value_gt"], color=colour, alpha=0.15, linewidth=0.8)
        median = sub.groupby("year")["value_gt"].median()
        n = sub[["model", "scenario"]].drop_duplicates().shape[0]
        ax.plot(
            median.index,
            median.values,
            color=colour,
            linewidth=2.5,
            label=f"{CATEGORY_LABELS[cat]} (n={n})",
        )
    ax.axhline(0, color="black", linewidth=1)
    ax.set_xlabel("Year")
    ax.set_ylabel("Global net CO$_2$ emissions (Gt CO$_2$/yr)")
    ax.set_title("Net CO$_2$ pathways by temperature category\n(thin lines: scenarios, thick: median)" + note)
    ax.legend(frameon=False, loc="upper right")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def plot_timing(nz: pd.DataFrame, path: Path, note: str = "") -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6, 4.5))
    data, colours, labels = [], [], []
    for cat in CATEGORIES:
        vals = nz.loc[nz["category"] == cat, "net_zero_year"].dropna().to_numpy()
        if len(vals):
            data.append(vals)
            colours.append(CATEGORY_COLOURS[cat])
            labels.append(cat)
    box = ax.boxplot(data, patch_artist=True, tick_labels=labels, widths=0.5)
    for patch, colour in zip(box["boxes"], colours):
        patch.set_facecolor(colour)
        patch.set_alpha(0.6)
    for median in box["medians"]:
        median.set_color("black")
    ax.set_ylabel("Year net CO$_2$ reaches zero")
    ax.set_title("When does net-zero CO$_2$ happen?" + note)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# --------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------
def run(demo: bool, out_dir: Path) -> pd.DataFrame:
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "demo_" if demo else ""
    note = "\nSYNTHETIC DEMO DATA, NOT AR6 RESULTS" if demo else ""

    raw = make_demo_data() if demo else load_ar6()
    df = prepare(raw)
    if df.empty:
        raise SystemExit("No scenarios left after filtering. Check the data and category names.")

    nz = net_zero_years(df)
    summary = summarise(nz)

    nz.to_csv(out_dir / f"{prefix}net_zero_years.csv", index=False)
    summary.to_csv(out_dir / f"{prefix}summary.csv", index=False)
    plot_pathways(df, out_dir / f"{prefix}net_co2_pathways.png", note)
    plot_timing(nz, out_dir / f"{prefix}net_zero_timing.png", note)

    print(summary.to_string(index=False))
    print(f"\nFiles written to: {out_dir.resolve()}")
    return summary


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--demo", action="store_true", help="use synthetic data (no internet needed)")
    parser.add_argument("--out", type=Path, default=Path("outputs"), help="output folder")
    args = parser.parse_args(argv)
    run(args.demo, args.out)


if __name__ == "__main__":
    main()
