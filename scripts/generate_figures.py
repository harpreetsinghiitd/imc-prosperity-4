#!/usr/bin/env python3

import csv
import io
import json
import statistics
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

import analyze_round_four as round_four_analysis


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "docs" / "assets"
COLORS = {
    "navy": "#14213d",
    "blue": "#2563eb",
    "teal": "#0f9d8a",
    "orange": "#f59e0b",
    "red": "#dc2626",
    "purple": "#7c3aed",
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


def round_two_research_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    round_dir, _, result = next(item for item in rounds if item[1]["round"] == 2)
    rows = list(csv.DictReader(io.StringIO(result["activitiesLog"]), delimiter=";"))
    by_product = defaultdict(list)
    for row in rows:
        by_product[row["product"]].append(row)

    osmium = by_product["ASH_COATED_OSMIUM"]
    osmium_fair = []
    fair = 10_000.0
    for row in osmium:
        fair = 0.01 * float(row["mid_price"]) + 0.99 * fair
        osmium_fair.append(fair)

    pepper = by_product["INTARIAN_PEPPER_ROOT"]
    pepper_times = [int(row["timestamp"]) for row in pepper]
    pepper_mids = [float(row["mid_price"]) for row in pepper]
    mean_time = statistics.mean(pepper_times)
    mean_mid = statistics.mean(pepper_mids)
    slope = sum(
        (timestamp - mean_time) * (midpoint - mean_mid)
        for timestamp, midpoint in zip(pepper_times, pepper_mids)
    ) / sum((timestamp - mean_time) ** 2 for timestamp in pepper_times)
    intercept = mean_mid - slope * mean_time

    submission_log = json.loads(
        (round_dir / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    position_changes = defaultdict(int)
    for trade in submission_log["tradeHistory"]:
        if trade["symbol"] != "INTARIAN_PEPPER_ROOT":
            continue
        timestamp = int(trade["timestamp"])
        if trade.get("buyer") == "SUBMISSION":
            position_changes[timestamp] += int(trade["quantity"])
        if trade.get("seller") == "SUBMISSION":
            position_changes[timestamp] -= int(trade["quantity"])
    pepper_positions = []
    position = 0
    for timestamp in pepper_times:
        position += position_changes[timestamp]
        pepper_positions.append(position)

    sample = range(0, len(osmium), 10)
    progress = [int(osmium[index]["timestamp"]) / 10_000 for index in sample]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)

    axes[0, 0].plot(
        progress,
        [float(osmium[index]["mid_price"]) for index in sample],
        color=COLORS["blue"],
        linewidth=1.15,
        alpha=0.8,
        label="Observed midpoint",
    )
    axes[0, 0].plot(
        progress,
        [osmium_fair[index] for index in sample],
        color=COLORS["orange"],
        linewidth=2,
        label="1% fair-value EMA",
    )
    axes[0, 0].set_title("Osmium: a slow center for a bounded market")
    axes[0, 0].set_xlabel("Round progress (%)")
    axes[0, 0].set_ylabel("Price (XIRECS)")
    axes[0, 0].legend(frameon=False)
    axes[0, 0].grid(color=COLORS["grid"], linewidth=0.6)

    axes[0, 1].plot(
        progress,
        [pepper_mids[index] for index in sample],
        color=COLORS["blue"],
        linewidth=1.2,
        label="Observed midpoint",
    )
    axes[0, 1].plot(
        progress,
        [intercept + slope * pepper_times[index] for index in sample],
        color=COLORS["orange"],
        linewidth=2,
        linestyle="--",
        label=f"Fitted trend (slope {slope:.6f})",
    )
    axes[0, 1].set_title("Pepper Root: the directional regime persisted")
    axes[0, 1].set_xlabel("Round progress (%)")
    axes[0, 1].set_ylabel("Price (XIRECS)")
    axes[0, 1].legend(frameon=False)
    axes[0, 1].grid(color=COLORS["grid"], linewidth=0.6)

    axes[1, 0].step(
        progress,
        [pepper_positions[index] for index in sample],
        where="post",
        color=COLORS["teal"],
        linewidth=1.5,
        label="Recorded position",
    )
    axes[1, 0].axhline(
        80,
        color=COLORS["orange"],
        linewidth=1.5,
        linestyle="--",
        label="Strategy target: +80",
    )
    axes[1, 0].set_ylim(-4, 85)
    axes[1, 0].set_title("Pepper Root: acquire, recycle, replenish")
    axes[1, 0].set_xlabel("Round progress (%)")
    axes[1, 0].set_ylabel("Position")
    axes[1, 0].legend(frameon=False)
    axes[1, 0].grid(color=COLORS["grid"], linewidth=0.6)

    product_styles = {
        "ASH_COATED_OSMIUM": ("Ash Coated Osmium", COLORS["teal"]),
        "INTARIAN_PEPPER_ROOT": ("Intarian Pepper Root", COLORS["blue"]),
    }
    for product, (label, color) in product_styles.items():
        product_rows = by_product[product]
        axes[1, 1].plot(
            progress,
            [float(product_rows[index]["profit_and_loss"]) for index in sample],
            color=color,
            linewidth=1.8,
            label=label,
        )
    axes[1, 1].set_title("Both product engines contributed throughout the round")
    axes[1, 1].set_xlabel("Round progress (%)")
    axes[1, 1].set_ylabel("Product P&L (XIRECS)")
    axes[1, 1].yaxis.set_major_formatter(FuncFormatter(money))
    axes[1, 1].legend(frameon=False)
    axes[1, 1].grid(color=COLORS["grid"], linewidth=0.6)

    fig.suptitle("Round 2 research evidence", fontsize=16)
    save(fig, "round-02-research.svg")


def round_three_research_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    round_dir, _, result = next(item for item in rounds if item[1]["round"] == 3)
    rows = list(csv.DictReader(io.StringIO(result["activitiesLog"]), delimiter=";"))
    by_product = defaultdict(list)
    for row in rows:
        by_product[row["product"]].append(row)

    hydrogel = by_product["HYDROGEL_PACK"]
    velvetfruit = by_product["VELVETFRUIT_EXTRACT"]
    vev_5000 = by_product["VEV_5000"]
    timestamps = [int(row["timestamp"]) for row in hydrogel]
    progress_all = [timestamp / 10_000 for timestamp in timestamps]
    hydrogel_mid = [float(row["mid_price"]) for row in hydrogel]
    velvetfruit_mid = [float(row["mid_price"]) for row in velvetfruit]
    vev_5000_mid = [float(row["mid_price"]) for row in vev_5000]

    hydrogel_fair = []
    fair = 9_985.0
    for midpoint in hydrogel_mid:
        fair = round(0.0002 * midpoint + 0.9998 * fair, 2)
        hydrogel_fair.append(fair)
    vev_5000_fair = [
        0.6536 * midpoint - 3_176.2 for midpoint in velvetfruit_mid
    ]

    submission_log = json.loads(
        (round_dir / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    position_changes = defaultdict(lambda: defaultdict(int))
    for trade in submission_log["tradeHistory"]:
        if trade.get("buyer") != "SUBMISSION" and trade.get("seller") != "SUBMISSION":
            continue
        timestamp = int(trade["timestamp"])
        product = trade["symbol"]
        quantity = int(trade["quantity"])
        if trade.get("buyer") == "SUBMISSION":
            position_changes[timestamp][product] += quantity
        if trade.get("seller") == "SUBMISSION":
            position_changes[timestamp][product] -= quantity

    delta_estimates = {
        "VEV_4000": 1.0,
        "VEV_4500": 0.82,
        "VEV_5000": 0.6536,
        "VEV_5100": 0.5774,
        "VEV_5200": 0.4367,
        "VEV_5300": 0.2727,
        "VEV_5400": 0.1289,
        "VEV_5500": 0.0549,
        "VEV_6000": 0.01,
        "VEV_6500": 0.001,
    }
    position = defaultdict(int)
    portfolio_delta = []
    for timestamp in timestamps:
        for product, change in position_changes[timestamp].items():
            position[product] += change
        portfolio_delta.append(
            position["VELVETFRUIT_EXTRACT"]
            + sum(
                position[product] * delta
                for product, delta in delta_estimates.items()
            )
        )

    sample = range(0, len(timestamps), 10)
    progress = [progress_all[index] for index in sample]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)

    axes[0, 0].plot(
        progress,
        [hydrogel_mid[index] for index in sample],
        color=COLORS["blue"],
        linewidth=1.15,
        label="Observed midpoint",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] for index in sample],
        color=COLORS["orange"],
        linewidth=1.8,
        label="Persisted 0.02% EMA fair",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] + 40 for index in sample],
        color=COLORS["red"],
        linewidth=1,
        linestyle="--",
        label="Entry band: fair ±40",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] - 40 for index in sample],
        color=COLORS["red"],
        linewidth=1,
        linestyle="--",
    )
    axes[0, 0].set_title("Hydrogel: slow center, wide entry band")
    axes[0, 0].set_xlabel("Round progress (%)")
    axes[0, 0].set_ylabel("Price (XIRECS)")
    axes[0, 0].legend(frameon=False, fontsize=9)
    axes[0, 0].grid(color=COLORS["grid"], linewidth=0.6)

    axes[0, 1].plot(
        progress,
        [velvetfruit_mid[index] for index in sample],
        color=COLORS["blue"],
        linewidth=1.2,
        label="Observed midpoint",
    )
    axes[0, 1].axhline(
        5_249,
        color=COLORS["orange"],
        linewidth=1.8,
        label="Fixed center: 5,249",
    )
    axes[0, 1].axhline(
        5_269,
        color=COLORS["red"],
        linewidth=1,
        linestyle="--",
        label="Entry band: center ±20",
    )
    axes[0, 1].axhline(
        5_229,
        color=COLORS["red"],
        linewidth=1,
        linestyle="--",
    )
    axes[0, 1].set_title("Velvetfruit: directional mean reversion")
    axes[0, 1].set_xlabel("Round progress (%)")
    axes[0, 1].set_ylabel("Price (XIRECS)")
    axes[0, 1].legend(frameon=False, fontsize=9)
    axes[0, 1].grid(color=COLORS["grid"], linewidth=0.6)

    axes[1, 0].plot(
        progress,
        [vev_5000_mid[index] for index in sample],
        color=COLORS["blue"],
        linewidth=1.2,
        label="Observed VEV 5000 midpoint",
    )
    axes[1, 0].plot(
        progress,
        [vev_5000_fair[index] for index in sample],
        color=COLORS["orange"],
        linewidth=1.8,
        label="Code model: 0.6536 × spot − 3,176.2",
    )
    axes[1, 0].set_title("VEV 5000: local linear relative value")
    axes[1, 0].set_xlabel("Round progress (%)")
    axes[1, 0].set_ylabel("Voucher value (XIRECS)")
    axes[1, 0].legend(frameon=False, fontsize=9)
    axes[1, 0].grid(color=COLORS["grid"], linewidth=0.6)

    axes[1, 1].plot(
        progress,
        [portfolio_delta[index] for index in sample],
        color=COLORS["teal"],
        linewidth=1.5,
        label="Estimated portfolio delta",
    )
    axes[1, 1].axhline(
        1_000,
        color=COLORS["red"],
        linewidth=1.2,
        linestyle="--",
        label="Emergency gate: ±1,000",
    )
    axes[1, 1].axhline(
        -1_000,
        color=COLORS["red"],
        linewidth=1.2,
        linestyle="--",
    )
    axes[1, 1].axhline(
        500,
        color=COLORS["orange"],
        linewidth=1,
        linestyle=":",
        label="Post-hedge target: ±500",
    )
    axes[1, 1].axhline(
        -500,
        color=COLORS["orange"],
        linewidth=1,
        linestyle=":",
    )
    axes[1, 1].axvspan(
        92,
        100,
        color=COLORS["grid"],
        alpha=0.5,
        label="Exposure scaling",
    )
    axes[1, 1].set_ylim(-1_100, 1_100)
    axes[1, 1].set_title("Portfolio delta remained inside the emergency gate")
    axes[1, 1].set_xlabel("Round progress (%)")
    axes[1, 1].set_ylabel("Estimated delta")
    axes[1, 1].legend(frameon=False, fontsize=8, ncol=2)
    axes[1, 1].grid(color=COLORS["grid"], linewidth=0.6)

    fig.suptitle("Round 3 research evidence", fontsize=16)
    save(fig, "round-03-research.svg")


def round_four_research_chart(rounds: list[tuple[Path, dict, dict]]) -> None:
    round_dir, _, result = next(item for item in rounds if item[1]["round"] == 4)
    rows = list(csv.DictReader(io.StringIO(result["activitiesLog"]), delimiter=";"))
    by_product = defaultdict(list)
    rows_by_key = {}
    for row in rows:
        by_product[row["product"]].append(row)
        rows_by_key[(int(row["timestamp"]), row["product"])] = row

    submission_log = json.loads(
        (round_dir / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    market_trades, own_trades = round_four_analysis.split_trade_tape(
        submission_log["tradeHistory"]
    )
    position_before, _, _ = round_four_analysis.position_state(
        submission_log["tradeHistory"]
    )
    strategy, trader = round_four_analysis.load_strategy()
    trader_data = ""
    timestamps = list(range(0, 1_000_000, 100))
    progress_all = [timestamp / 10_000 for timestamp in timestamps]
    hydrogel_top = []
    hydrogel_stable = []
    hydrogel_fair = []
    velvetfruit_spot = []
    velvetfruit_center = []
    zones = []
    sigma_path = []
    iv_minimum = []
    iv_maximum = []

    for timestamp in timestamps:
        depths = {
            product: round_four_analysis.order_depth(rows_by_key[(timestamp, product)])
            for product in round_four_analysis.PRODUCTS
        }
        position = {
            product: position_before[timestamp].get(product, 0)
            for product in round_four_analysis.PRODUCTS
        }
        state = round_four_analysis.TradingState(
            timestamp=timestamp,
            traderData=trader_data,
            order_depths=depths,
            position=position,
            market_trades=dict(market_trades.get(timestamp, {})),
            own_trades=dict(own_trades.get(timestamp, {})),
        )
        _, _, trader_data = trader.run(state)
        saved = json.loads(trader_data)

        hydrogel_top.append(
            round_four_analysis.best_mid(depths["HYDROGEL_PACK"])
        )
        hydrogel_stable.append(
            round_four_analysis.stable_mid(depths["HYDROGEL_PACK"])
        )
        hydrogel_fair.append(
            float(saved["hg"]) + strategy.M38_SCALE * float(saved["m38"])
        )
        spot = round_four_analysis.best_mid(depths["VELVETFRUIT_EXTRACT"])
        center = float(saved["ve"]) + strategy.VE_CP_SCALE * float(saved["vcp"])
        velvetfruit_spot.append(spot)
        velvetfruit_center.append(center)
        sigma_path.append(float(saved["sig"]))

        trend_up = int(saved["tc"]) >= strategy.TREND_TICKS
        crash_suppress = int(saved["ccd"]) > 0
        if spot < center - strategy.ZONE_OFF:
            zone = "long"
        elif spot > center + (
            strategy.ZONE_OFF_TREND if trend_up else strategy.ZONE_OFF
        ):
            zone = "short"
        elif center - strategy.FLAT_OFF <= spot <= center + strategy.FLAT_OFF:
            zone = "flat"
        else:
            zone = "wait"
        if crash_suppress and zone == "long":
            zone = "guarded"
        zones.append(zone)

        fraction = timestamp / 999_900 if timestamp < 999_900 else 1
        tte = 4 / 252 + fraction * (3 / 252 - 4 / 252)
        ivs = []
        for product in round_four_analysis.ATM_VOUCHERS:
            midpoint = round_four_analysis.best_mid(depths[product])
            iv = strategy.bs_iv(
                midpoint, spot, strategy.STRIKES[product], tte
            )
            if iv and 0.05 < iv < 2:
                ivs.append(iv)
        iv_minimum.append(min(ivs) if ivs else float("nan"))
        iv_maximum.append(max(ivs) if ivs else float("nan"))

    sample = list(range(0, len(timestamps), 10))
    progress = [progress_all[index] for index in sample]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), constrained_layout=True)

    axes[0, 0].plot(
        progress,
        [hydrogel_top[index] for index in sample],
        color=COLORS["grid"],
        linewidth=0.9,
        label="Top-of-book midpoint",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_stable[index] for index in sample],
        color=COLORS["blue"],
        linewidth=1.1,
        alpha=0.8,
        label="Outer-book stable midpoint",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] for index in sample],
        color=COLORS["orange"],
        linewidth=2,
        label="Slow EMA + bounded flow",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] + 31 for index in sample],
        color=COLORS["red"],
        linewidth=0.9,
        linestyle="--",
        label="Entry band: fair ±31",
    )
    axes[0, 0].plot(
        progress,
        [hydrogel_fair[index] - 31 for index in sample],
        color=COLORS["red"],
        linewidth=0.9,
        linestyle="--",
    )
    axes[0, 0].set_title("Hydrogel: stable observation, slow anchor")
    axes[0, 0].set_xlabel("Round progress (%)")
    axes[0, 0].set_ylabel("Price (XIRECS)")
    axes[0, 0].legend(frameon=False, fontsize=8)
    axes[0, 0].grid(color=COLORS["grid"], linewidth=0.6)

    axes[0, 1].plot(
        progress,
        [velvetfruit_spot[index] for index in sample],
        color=COLORS["navy"],
        linewidth=1.1,
        label="Velvetfruit midpoint",
    )
    axes[0, 1].plot(
        progress,
        [velvetfruit_center[index] for index in sample],
        color=COLORS["orange"],
        linewidth=1.8,
        label="Flow-adjusted center",
    )
    zone_styles = {
        "long": ("Long zone", COLORS["teal"]),
        "short": ("Short zone", COLORS["red"]),
        "flat": ("Flatten zone", COLORS["orange"]),
        "guarded": ("Long entry guarded", COLORS["purple"]),
    }
    for zone, (label, color) in zone_styles.items():
        points = [index for index in sample if zones[index] == zone]
        axes[0, 1].scatter(
            [progress_all[index] for index in points],
            [velvetfruit_spot[index] for index in points],
            s=7,
            color=color,
            alpha=0.65,
            label=label,
        )
    axes[0, 1].set_title("Shared regime proposed targets across eight routes")
    axes[0, 1].set_xlabel("Round progress (%)")
    axes[0, 1].set_ylabel("Price (XIRECS)")
    axes[0, 1].legend(frameon=False, fontsize=7, ncol=2)
    axes[0, 1].grid(color=COLORS["grid"], linewidth=0.6)

    axes[1, 0].fill_between(
        progress,
        [100 * iv_minimum[index] for index in sample],
        [100 * iv_maximum[index] for index in sample],
        color=COLORS["grid"],
        alpha=0.7,
        label="Valid cross-strike IV range",
    )
    axes[1, 0].plot(
        progress,
        [100 * sigma_path[index] for index in sample],
        color=COLORS["blue"],
        linewidth=2,
        label="2% common-volatility EMA",
    )
    axes[1, 0].set_title("Up to six strikes formed a live volatility consensus")
    axes[1, 0].set_xlabel("Round progress (%)")
    axes[1, 0].set_ylabel("Implied volatility (%)")
    axes[1, 0].legend(frameon=False, fontsize=8)
    axes[1, 0].grid(color=COLORS["grid"], linewidth=0.6)

    group_values = [
        float(by_product["HYDROGEL_PACK"][-1]["profit_and_loss"]),
        float(by_product["VELVETFRUIT_EXTRACT"][-1]["profit_and_loss"]),
        float(by_product["VEV_4000"][-1]["profit_and_loss"]),
        sum(
            float(by_product[product][-1]["profit_and_loss"])
            for product in round_four_analysis.ZONE_VOUCHERS
        ),
    ]
    group_labels = [
        "Hydrogel",
        "Velvetfruit",
        "VEV 4000\nwall-mid",
        "Zone vouchers\n4500–5500",
    ]
    bars = axes[1, 1].bar(
        group_labels,
        group_values,
        color=[COLORS["blue"], COLORS["teal"], COLORS["orange"], COLORS["purple"]],
    )
    for bar, value in zip(bars, group_values):
        axes[1, 1].text(
            bar.get_x() + bar.get_width() / 2,
            value,
            f"{value:,.0f}",
            ha="center",
            va="bottom",
            fontsize=9,
        )
    axes[1, 1].set_title("Every active strategy block finished positive")
    axes[1, 1].set_ylabel("Final P&L (XIRECS)")
    axes[1, 1].yaxis.set_major_formatter(FuncFormatter(money))
    axes[1, 1].grid(axis="y", color=COLORS["grid"], linewidth=0.6)
    axes[1, 1].set_axisbelow(True)

    fig.suptitle(
        "Round 4 — shared regime, bounded flow, and a theory veto", fontsize=16
    )
    save(fig, "round-04-research.svg")


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
    round_two_research_chart(rounds)
    round_three_research_chart(rounds)
    round_four_research_chart(rounds)
    product_charts(rounds)
    print(f"generated {len(rounds) + 6} figures in {ASSETS.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
