#!/usr/bin/env python3

import csv
import importlib.util
import io
import json
import math
import statistics
import sys
import types
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUND_DIR = ROOT / "rounds" / "round-01"
PRODUCTS = ("ASH_COATED_OSMIUM", "INTARIAN_PEPPER_ROOT")


@dataclass
class Order:
    symbol: str
    price: int
    quantity: int


class OrderDepth:
    def __init__(
        self,
        buy_orders: dict[int, int] | None = None,
        sell_orders: dict[int, int] | None = None,
    ) -> None:
        self.buy_orders = buy_orders or {}
        self.sell_orders = sell_orders or {}


@dataclass
class TradingState:
    timestamp: int
    traderData: str
    order_depths: dict[str, OrderDepth]
    position: dict[str, int]


def activity_rows(result: dict[str, object]) -> list[dict[str, str]]:
    return list(
        csv.DictReader(io.StringIO(str(result["activitiesLog"])), delimiter=";")
    )


def levels(row: dict[str, str], side: str) -> list[tuple[int, int]]:
    output = []
    for index in range(1, 4):
        price = row.get(f"{side}_price_{index}", "")
        volume = row.get(f"{side}_volume_{index}", "")
        if price and volume:
            output.append((int(float(price)), int(float(volume))))
    return output


def order_depth(row: dict[str, str]) -> OrderDepth:
    bids = {price: volume for price, volume in levels(row, "bid")}
    asks = {price: -volume for price, volume in levels(row, "ask")}
    return OrderDepth(bids, asks)


def linear_fit(xs: list[int], ys: list[float]) -> dict[str, float]:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance_x = sum((value - mean_x) ** 2 for value in xs)
    slope = (
        sum((x_value - mean_x) * (y_value - mean_y) for x_value, y_value in zip(xs, ys))
        / variance_x
    )
    intercept = mean_y - slope * mean_x
    residuals = [
        y_value - (intercept + slope * x_value) for x_value, y_value in zip(xs, ys)
    ]
    total_variance = sum((value - mean_y) ** 2 for value in ys)
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": 1 - sum(value**2 for value in residuals) / total_variance,
        "rmse": math.sqrt(sum(value**2 for value in residuals) / count),
    }


def pnl_path_stats(rows: list[tuple[int, float]]) -> dict[str, float]:
    fit = linear_fit([timestamp for timestamp, _ in rows], [value for _, value in rows])
    increments = [rows[index][1] - rows[index - 1][1] for index in range(1, len(rows))]
    return {
        "r_squared": fit["r_squared"],
        "slope_per_100k": fit["slope"] * 100_000,
        "positive_increment_pct": 100
        * sum(value > 0 for value in increments)
        / len(increments),
    }


def reconstruct_fair_values(
    rows: list[dict[str, str]],
) -> tuple[dict[int, float], dict[str, object]]:
    previous = None
    fair_values = {}
    sources = Counter()
    large_wall_any = 0
    large_wall_both = 0
    secondary_signature = 0
    both_signature_classes = 0
    for row in rows:
        timestamp = int(row["timestamp"])
        bids = levels(row, "bid")
        asks = levels(row, "ask")
        if not bids and not asks:
            if previous is not None:
                fair_values[timestamp] = previous
            sources["stored_fair_value"] += 1
            continue

        large_estimates = [price + 10.5 for price, volume in bids if volume >= 20] + [
            price - 10.5 for price, volume in asks if volume >= 20
        ]
        if large_estimates:
            large_wall_any += 1
        if any(volume >= 20 for _, volume in bids) and any(
            volume >= 20 for _, volume in asks
        ):
            large_wall_both += 1
        large_fair = (
            sum(large_estimates) / len(large_estimates) if large_estimates else None
        )
        reference = large_fair or previous
        if reference is None:
            if bids and asks:
                reference = (bids[0][0] + asks[0][0]) / 2
            elif bids:
                reference = bids[0][0] + 8
            else:
                reference = asks[0][0] - 8

        estimates = []
        found_secondary = False
        for price, volume in bids:
            if 10 <= volume <= 15 and abs(price - (reference - 8)) <= 3:
                estimates.append((price + 8, 2.0))
                found_secondary = True
            elif volume >= 20:
                estimates.append((price + 10.5, 1.0))
        for price, volume in asks:
            if 10 <= volume <= 15 and abs(price - (reference + 8)) <= 3:
                estimates.append((price - 8, 2.0))
                found_secondary = True
            elif volume >= 20:
                estimates.append((price - 10.5, 1.0))
        if found_secondary:
            secondary_signature += 1
        if large_estimates and found_secondary:
            both_signature_classes += 1

        if estimates:
            total_weight = sum(weight for _, weight in estimates)
            fair_value = (
                sum(estimate * weight for estimate, weight in estimates) / total_weight
            )
            sources["book_signature"] += 1
        elif bids and asks:
            fair_value = (bids[0][0] + asks[0][0]) / 2
            sources["midpoint_fallback"] += 1
        elif bids:
            fair_value = bids[0][0] + 10.5
            sources["bid_fallback"] += 1
        else:
            fair_value = asks[0][0] - 10.5
            sources["ask_fallback"] += 1
        previous = fair_value
        fair_values[timestamp] = fair_value

    row_count = len(rows)
    valid_differences = [
        abs(fair_values[int(row["timestamp"])] - float(row["mid_price"]))
        for row in rows
        if float(row["mid_price"]) > 0 and int(row["timestamp"]) in fair_values
    ]
    fair_series = [
        fair_values[int(row["timestamp"])]
        for row in rows
        if int(row["timestamp"]) in fair_values
    ]
    mid_series = [
        float(row["mid_price"]) for row in rows if float(row["mid_price"]) > 0
    ]
    return fair_values, {
        "top_three_snapshot_count": row_count,
        "fair_value_source_counts": dict(sources),
        "book_signature_pct": 100 * sources["book_signature"] / row_count,
        "large_wall_any_pct": 100 * large_wall_any / row_count,
        "large_wall_both_sides_pct": 100 * large_wall_both / row_count,
        "secondary_signature_pct": 100 * secondary_signature / row_count,
        "both_signature_classes_pct": 100 * both_signature_classes / row_count,
        "median_absolute_fair_mid_gap": statistics.median(valid_differences),
        "mean_absolute_fair_change": statistics.mean(
            abs(fair_series[index] - fair_series[index - 1])
            for index in range(1, len(fair_series))
        ),
        "mean_absolute_mid_change": statistics.mean(
            abs(mid_series[index] - mid_series[index - 1])
            for index in range(1, len(mid_series))
        ),
    }


def submission_fills(
    trades: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    output = defaultdict(list)
    for trade in trades:
        if trade.get("buyer") == "SUBMISSION" or trade.get("seller") == "SUBMISSION":
            output[str(trade["symbol"])].append(trade)
    return output


def fill_summary(
    product: str,
    trades: list[dict[str, object]],
    fair_values: dict[int, float] | None = None,
) -> dict[str, object]:
    buys = [trade for trade in trades if trade.get("buyer") == "SUBMISSION"]
    sells = [trade for trade in trades if trade.get("seller") == "SUBMISSION"]
    buy_volume = sum(int(trade["quantity"]) for trade in buys)
    sell_volume = sum(int(trade["quantity"]) for trade in sells)
    buy_cost = sum(float(trade["price"]) * int(trade["quantity"]) for trade in buys)
    sell_value = sum(float(trade["price"]) * int(trade["quantity"]) for trade in sells)
    output = {
        "fill_events": len(trades),
        "first_fill_timestamp": min(int(trade["timestamp"]) for trade in trades),
        "last_fill_timestamp": max(int(trade["timestamp"]) for trade in trades),
        "buy_events": len(buys),
        "sell_events": len(sells),
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "buy_vwap": buy_cost / buy_volume if buy_volume else None,
        "sell_vwap": sell_value / sell_volume if sell_volume else None,
        "average_fill_size": sum(int(trade["quantity"]) for trade in trades)
        / len(trades),
    }
    if product == "ASH_COATED_OSMIUM" and fair_values is not None:
        edges = []
        for trade in buys:
            edge = fair_values[int(trade["timestamp"])] - float(trade["price"])
            edges.extend([edge] * int(trade["quantity"]))
        for trade in sells:
            edge = float(trade["price"]) - fair_values[int(trade["timestamp"])]
            edges.extend([edge] * int(trade["quantity"]))
        output["volume_weighted_edge_to_fair"] = statistics.mean(edges)
        output["matched_flow_pct"] = (
            100 * min(buy_volume, sell_volume) / max(buy_volume, sell_volume)
        )
        position = 0
        observed_positions = [position]
        for trade in sorted(trades, key=lambda item: int(item["timestamp"])):
            if trade.get("buyer") == "SUBMISSION":
                position += int(trade["quantity"])
            if trade.get("seller") == "SUBMISSION":
                position -= int(trade["quantity"])
            observed_positions.append(position)
        output["observed_position_min"] = min(observed_positions)
        output["observed_position_max"] = max(observed_positions)
    return output


def load_trader() -> object:
    module = types.ModuleType("datamodel")
    module.Order = Order
    module.OrderDepth = OrderDepth
    module.TradingState = TradingState
    sys.modules["datamodel"] = module
    spec = importlib.util.spec_from_file_location(
        "round_one_trader", ROUND_DIR / "trader.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Round 1 trader")
    trader_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trader_module)
    return trader_module.Trader()


def replay_top_three_snapshots(
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    trades: list[dict[str, object]],
) -> dict[str, object]:
    position_changes = defaultdict(lambda: defaultdict(int))
    for trade in trades:
        timestamp = int(trade["timestamp"])
        product = str(trade["symbol"])
        quantity = int(trade["quantity"])
        if trade.get("buyer") == "SUBMISSION":
            position_changes[timestamp][product] += quantity
        if trade.get("seller") == "SUBMISSION":
            position_changes[timestamp][product] -= quantity

    position = defaultdict(int)
    trader_data = ""
    trader = load_trader()
    order_counts = Counter()
    marketable_snapshot_counts = Counter()
    side_capacity_passed = True
    for timestamp in range(0, 1_000_000, 100):
        depths = {
            product: order_depth(rows_by_key[(timestamp, product)])
            for product in PRODUCTS
        }
        state = TradingState(timestamp, trader_data, depths, dict(position))
        orders_by_product, _, trader_data = trader.run(state)
        for product, orders in orders_by_product.items():
            order_counts[product] += len(orders)
            best_bid = max(depths[product].buy_orders, default=None)
            best_ask = min(depths[product].sell_orders, default=None)
            if any(
                (
                    order.quantity > 0
                    and best_ask is not None
                    and order.price >= best_ask
                )
                or (
                    order.quantity < 0
                    and best_bid is not None
                    and order.price <= best_bid
                )
                for order in orders
            ):
                marketable_snapshot_counts[product] += 1
            buy_quantity = sum(order.quantity for order in orders if order.quantity > 0)
            sell_quantity = sum(
                -order.quantity for order in orders if order.quantity < 0
            )
            if buy_quantity > 80 - position[product]:
                side_capacity_passed = False
            if sell_quantity > 80 + position[product]:
                side_capacity_passed = False
        for product, change in position_changes[timestamp].items():
            position[product] += change

    return {
        "snapshots_replayed": 10_000,
        "top_three_book_only": True,
        "completed_without_exception": True,
        "independent_side_capacity_passed": side_capacity_passed,
        "orders_returned": dict(order_counts),
        "snapshots_with_marketable_order": dict(marketable_snapshot_counts),
        "ending_positions_reconstructed": dict(position),
    }


def main() -> int:
    result = json.loads(
        (ROUND_DIR / "capsule" / "result.json").read_text(encoding="utf-8")
    )
    log = json.loads(
        (ROUND_DIR / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    rows = activity_rows(result)
    rows_by_product = defaultdict(list)
    rows_by_key = {}
    for row in rows:
        rows_by_product[row["product"]].append(row)
        rows_by_key[(int(row["timestamp"]), row["product"])] = row

    pepper_rows = [
        row
        for row in rows_by_product["INTARIAN_PEPPER_ROOT"]
        if float(row["mid_price"]) > 0 and levels(row, "bid") and levels(row, "ask")
    ]
    timestamps = [int(row["timestamp"]) for row in pepper_rows]
    mids = [float(row["mid_price"]) for row in pepper_rows]
    pepper_fit = linear_fit(timestamps, mids)
    encoded_start = mids[0]
    encoded_residuals = [
        mid - (encoded_start + 0.001 * timestamp)
        for timestamp, mid in zip(timestamps, mids)
    ]

    osmium_rows = rows_by_product["ASH_COATED_OSMIUM"]
    fair_values, fair_summary = reconstruct_fair_values(osmium_rows)
    osmium_spreads = [
        levels(row, "ask")[0][0] - levels(row, "bid")[0][0]
        for row in osmium_rows
        if levels(row, "ask") and levels(row, "bid")
    ]
    fills = submission_fills(log["tradeHistory"])
    product_profit = {
        product: float(rows_by_product[product][-1]["profit_and_loss"])
        for product in PRODUCTS
    }
    graph_rows = [
        (int(row["timestamp"]), float(row["value"]))
        for row in csv.DictReader(io.StringIO(result["graphLog"]), delimiter=";")
    ]
    pepper_fill_summary = fill_summary(
        "INTARIAN_PEPPER_ROOT", fills["INTARIAN_PEPPER_ROOT"]
    )
    pepper_fill_summary["target_hold_pct"] = (
        100 * (999_900 - int(pepper_fill_summary["last_fill_timestamp"])) / 999_900
    )

    report = {
        "round": 1,
        "final_score": float(result["profit"]),
        "round_path": pnl_path_stats(graph_rows),
        "ash_coated_osmium": {
            "final_profit": product_profit["ASH_COATED_OSMIUM"],
            "median_spread": statistics.median(osmium_spreads),
            **fair_summary,
            **fill_summary(
                "ASH_COATED_OSMIUM",
                fills["ASH_COATED_OSMIUM"],
                fair_values,
            ),
        },
        "intarian_pepper_root": {
            "final_profit": product_profit["INTARIAN_PEPPER_ROOT"],
            "observed_mid_change": mids[-1] - mids[0],
            "fitted_slope": pepper_fit["slope"],
            "fitted_r_squared": pepper_fit["r_squared"],
            "fitted_rmse": pepper_fit["rmse"],
            "encoded_slope": 0.001,
            "encoded_model_rmse": math.sqrt(
                sum(value**2 for value in encoded_residuals) / len(encoded_residuals)
            ),
            **pepper_fill_summary,
        },
        "capsule_snapshot_replay": replay_top_three_snapshots(
            rows_by_key, log["tradeHistory"]
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
