#!/usr/bin/env python3

import csv
import io
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
COLORS = {
    "navy": "#14213d",
    "blue": "#2563eb",
    "teal": "#0f9d8a",
    "orange": "#f59e0b",
    "red": "#dc2626",
    "grid": "#d8dee9",
}


def money(value: float, _: int) -> str:
    return f"{value / 1000:.0f}k"


def load_rounds() -> list[tuple[Path, dict[str, object], dict[str, object]]]:
    rounds = []
    for round_dir in sorted(ROOT.glob("rounds/round-*")):
        summary = json.loads((round_dir / "summary.json").read_text(encoding="utf-8"))
        result = json.loads(
            (round_dir / "capsule" / "result.json").read_text(encoding="utf-8")
        )
        rounds.append((round_dir, summary, result))
    return rounds


def save(fig: plt.Figure, name: str) -> None:
    path = ASSETS / name
    fig.savefig(path, bbox_inches="tight", metadata={"Date": None})
    plt.close(fig)
    source = path.read_text(encoding="utf-8")
    path.write_text(
        "\n".join(line.rstrip() for line in source.splitlines()) + "\n",
        encoding="utf-8",
    )


def round_profit_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    labels = [f"Round {summary['round']}" for _, summary, _ in rounds]
    scores = [summary["final_score"] for _, summary, _ in rounds]
    x = list(range(len(labels)))
    fig, ax = plt.subplots(figsize=(10, 5.2))
    bars = ax.bar(x, scores, 0.58, color=COLORS["blue"], label="Final score")
    for bar, score in zip(bars, scores):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height(),
            f"{score:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    ax.axhline(0, color=COLORS["navy"], linewidth=0.8)
    ax.set_xticks(x, labels)
    ax.yaxis.set_major_formatter(FuncFormatter(money))
    ax.set_ylabel("XIRECS")
    ax.set_title("Recorded performance by round")
    ax.legend(frameon=False)
    ax.grid(axis="y", color=COLORS["grid"], linewidth=0.7)
    ax.set_axisbelow(True)
    save(fig, "round-profits.svg")


def pnl_curve_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    fig, axes = plt.subplots(3, 2, figsize=(12, 12), constrained_layout=True)
    axes = axes.ravel()
    for axis, (_, summary, result) in zip(axes, rounds):
        rows = list(csv.DictReader(io.StringIO(result["graphLog"]), delimiter=";"))
        timestamps = [int(row["timestamp"]) / 10_000 for row in rows]
        values = [float(row["value"]) for row in rows]
        axis.plot(timestamps, values, color=COLORS["blue"], linewidth=1.8)
        axis.axhline(0, color=COLORS["navy"], linewidth=0.7)
        axis.set_title(f"Round {summary['round']}")
        axis.set_xlabel("Round progress (%)")
        axis.set_ylabel("Recorded P&L")
        axis.yaxis.set_major_formatter(FuncFormatter(money))
        axis.grid(color=COLORS["grid"], linewidth=0.6)
    axes[-1].axis("off")
    fig.suptitle("Recorded P&L through each live run", fontsize=16)
    save(fig, "pnl-curves.svg")


def round_one_research_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    _, _, result = next(item for item in rounds if item[1]["round"] == 1)
    rows = list(csv.DictReader(io.StringIO(result["activitiesLog"]), delimiter=";"))
    by_product = defaultdict(list)
    for row in rows:
        by_product[row["product"]].append(row)

    pepper = [
        row for row in by_product["INTARIAN_PEPPER_ROOT"] if float(row["mid_price"]) > 0
    ]
    pepper_sample = pepper[::10]
    start_mid = float(pepper[0]["mid_price"])
    progress = [int(row["timestamp"]) / 10_000 for row in pepper_sample]
    observed = [float(row["mid_price"]) for row in pepper_sample]
    modeled = [start_mid + 0.001 * int(row["timestamp"]) for row in pepper_sample]

    fig, axes = plt.subplots(2, 1, figsize=(11, 8), constrained_layout=True)
    axes[0].plot(
        progress,
        observed,
        color=COLORS["blue"],
        linewidth=1.4,
        label="Observed midpoint",
    )
    axes[0].plot(
        progress,
        modeled,
        color=COLORS["orange"],
        linewidth=1.8,
        linestyle="--",
        label="Code model: start + 0.001 × timestamp",
    )
    axes[0].set_title("Pepper Root: observed midpoint versus the encoded path")
    axes[0].set_xlabel("Round progress (%)")
    axes[0].set_ylabel("Mid price (XIRECS)")
    axes[0].legend(frameon=False, ncol=2)
    axes[0].grid(color=COLORS["grid"], linewidth=0.6)

    product_styles = {
        "ASH_COATED_OSMIUM": ("Ash Coated Osmium", COLORS["teal"]),
        "INTARIAN_PEPPER_ROOT": ("Intarian Pepper Root", COLORS["blue"]),
    }
    for product, (label, color) in product_styles.items():
        product_rows = by_product[product][::10]
        product_progress = [int(row["timestamp"]) / 10_000 for row in product_rows]
        product_pnl = [float(row["profit_and_loss"]) for row in product_rows]
        axes[1].plot(
            product_progress,
            product_pnl,
            color=color,
            linewidth=1.8,
            label=label,
        )
    axes[1].set_title("Round 1 contribution through the live run")
    axes[1].set_xlabel("Round progress (%)")
    axes[1].set_ylabel("Product P&L (XIRECS)")
    axes[1].yaxis.set_major_formatter(FuncFormatter(money))
    axes[1].legend(frameon=False)
    axes[1].grid(color=COLORS["grid"], linewidth=0.6)
    save(fig, "round-01-research.svg")


def product_charts(rounds: list[tuple[Path, dict, dict]]) -> None:
    for _, summary, _ in rounds:
        products = sorted(summary["products"], key=lambda item: item["final_profit"])
        labels = [item["symbol"] for item in products]
        values = [item["final_profit"] for item in products]
        colors = [COLORS["teal"] if value >= 0 else COLORS["red"] for value in values]
        height = max(3.5, 0.26 * len(products) + 1.6)
        fig, ax = plt.subplots(figsize=(10, height))
        ax.barh(labels, values, color=colors)
        ax.axvline(0, color=COLORS["navy"], linewidth=0.8)
        ax.xaxis.set_major_formatter(FuncFormatter(money))
        ax.set_xlabel("Final product P&L (XIRECS)")
        ax.set_title(f"Round {summary['round']} product contribution")
        ax.grid(axis="x", color=COLORS["grid"], linewidth=0.6)
        ax.set_axisbelow(True)
        save(fig, f"product-pnl-round-{summary['round']:02}.svg")


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "svg.hashsalt": "imc-prosperity-4",
        }
    )
    rounds = load_rounds()
    round_profit_chart(rounds)
    pnl_curve_chart(rounds)
    round_one_research_chart(rounds)
    product_charts(rounds)
    print(f"generated {len(rounds) + 3} figures in {ASSETS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
