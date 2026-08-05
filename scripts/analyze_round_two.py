#!/usr/bin/env python3

import contextlib
import csv
import importlib.util
import io
import json
import math
import re
import statistics
import sys
import types
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUND_DIR = ROOT / "rounds" / "round-02"
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


def rows_from_semicolon_log(value: object) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(str(value)), delimiter=";"))


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


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    position = probability * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def linear_fit(xs: list[int], ys: list[float]) -> dict[str, float]:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance_x = sum((value - mean_x) ** 2 for value in xs)
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys)
    ) / variance_x
    intercept = mean_y - slope * mean_x
    residuals = [
        y_value - (intercept + slope * x_value)
        for x_value, y_value in zip(xs, ys)
    ]
    total_variance = sum((value - mean_y) ** 2 for value in ys)
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": 1 - sum(value**2 for value in residuals) / total_variance,
        "rmse": math.sqrt(sum(value**2 for value in residuals) / count),
    }


def pnl_path_stats(rows: list[dict[str, str]]) -> dict[str, object]:
    timestamps = [int(row["timestamp"]) for row in rows]
    values = [float(row["value"]) for row in rows]
    fit = linear_fit(timestamps, values)
    increments = [values[index] - values[index - 1] for index in range(1, len(values))]
    milestones = {}
    for level in (10_000, 25_000, 50_000, 75_000, 90_000, 96_000):
        milestones[str(level)] = next(
            timestamp
            for timestamp, value in zip(timestamps, values)
            if value >= level
        )
    minimum_index = min(range(len(values)), key=values.__getitem__)
    return {
        "sample_count": len(rows),
        "r_squared": fit["r_squared"],
        "slope_per_100k": fit["slope"] * 100_000,
        "positive_increments": sum(value > 0 for value in increments),
        "negative_increments": sum(value < 0 for value in increments),
        "positive_increment_pct": 100
        * sum(value > 0 for value in increments)
        / len(increments),
        "median_increment": statistics.median(increments),
        "minimum_value": values[minimum_index],
        "minimum_timestamp": timestamps[minimum_index],
        "milestone_timestamps": milestones,
    }


def market_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    valid = [
        row
        for row in rows
        if float(row["mid_price"]) > 0
        and levels(row, "bid")
        and levels(row, "ask")
    ]
    timestamps = [int(row["timestamp"]) for row in valid]
    mids = [float(row["mid_price"]) for row in valid]
    spreads = [
        levels(row, "ask")[0][0] - levels(row, "bid")[0][0] for row in valid
    ]
    fit = linear_fit(timestamps, mids)
    return {
        "two_sided_snapshots": len(valid),
        "opening_midpoint": mids[0],
        "final_midpoint": mids[-1],
        "midpoint_change": mids[-1] - mids[0],
        "minimum_midpoint": min(mids),
        "maximum_midpoint": max(mids),
        "mean_midpoint": statistics.mean(mids),
        "midpoint_stdev": statistics.pstdev(mids),
        "mean_spread": statistics.mean(spreads),
        "median_spread": statistics.median(spreads),
        "time_slope": fit["slope"],
        "time_r_squared": fit["r_squared"],
        "time_rmse": fit["rmse"],
    }


def submission_fills(
    trades: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    output = defaultdict(list)
    for trade in trades:
        if trade.get("buyer") == "SUBMISSION" or trade.get("seller") == "SUBMISSION":
            output[str(trade["symbol"])].append(trade)
    return output


def position_state(
    trades: list[dict[str, object]],
) -> tuple[dict[int, dict[str, int]], dict[str, list[int]], dict[str, int]]:
    changes = defaultdict(lambda: defaultdict(int))
    for trade in trades:
        timestamp = int(trade["timestamp"])
        product = str(trade["symbol"])
        quantity = int(trade["quantity"])
        if trade.get("buyer") == "SUBMISSION":
            changes[timestamp][product] += quantity
        if trade.get("seller") == "SUBMISSION":
            changes[timestamp][product] -= quantity

    position = defaultdict(int)
    before = {}
    after_paths = {product: [] for product in PRODUCTS}
    for timestamp in range(0, 1_000_000, 100):
        before[timestamp] = dict(position)
        for product, change in changes[timestamp].items():
            position[product] += change
        for product in PRODUCTS:
            after_paths[product].append(position[product])
    return before, after_paths, dict(position)


def classify_fills(
    product: str,
    trades: list[dict[str, object]],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
) -> dict[str, object]:
    categories = Counter()
    volumes = Counter()
    for trade in trades:
        row = rows_by_key[(int(trade["timestamp"]), product)]
        best_bid = levels(row, "bid")[0][0]
        best_ask = levels(row, "ask")[0][0]
        price = float(trade["price"])
        quantity = int(trade["quantity"])
        if trade.get("buyer") == "SUBMISSION":
            category = "aggressive_buy" if price >= best_ask else "passive_buy"
        else:
            category = "aggressive_sell" if price <= best_bid else "passive_sell"
        categories[category] += 1
        volumes[category] += quantity
    return {
        category: {"events": categories[category], "volume": volumes[category]}
        for category in (
            "aggressive_buy",
            "passive_buy",
            "aggressive_sell",
            "passive_sell",
        )
    }


def fill_summary(
    product: str,
    trades: list[dict[str, object]],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    position_path: list[int],
) -> dict[str, object]:
    buys = [trade for trade in trades if trade.get("buyer") == "SUBMISSION"]
    sells = [trade for trade in trades if trade.get("seller") == "SUBMISSION"]
    buy_volume = sum(int(trade["quantity"]) for trade in buys)
    sell_volume = sum(int(trade["quantity"]) for trade in sells)
    buy_cost = sum(float(trade["price"]) * int(trade["quantity"]) for trade in buys)
    sell_value = sum(float(trade["price"]) * int(trade["quantity"]) for trade in sells)
    result = {
        "fill_events": len(trades),
        "filled_units": buy_volume + sell_volume,
        "first_fill_timestamp": min(int(trade["timestamp"]) for trade in trades),
        "last_fill_timestamp": max(int(trade["timestamp"]) for trade in trades),
        "buy_events": len(buys),
        "sell_events": len(sells),
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "buy_vwap": buy_cost / buy_volume,
        "sell_vwap": sell_value / sell_volume,
        "vwap_separation": sell_value / sell_volume - buy_cost / buy_volume,
        "average_fill_size": (buy_volume + sell_volume) / len(trades),
        "ending_position": position_path[-1],
        "position_minimum": min(position_path),
        "position_maximum": max(position_path),
        "position_mean": statistics.mean(position_path),
        "position_median": statistics.median(position_path),
        "mean_absolute_position": statistics.mean(
            abs(value) for value in position_path
        ),
        "time_at_positive_limit_pct": 100
        * sum(value == 80 for value in position_path)
        / len(position_path),
        "actual_fill_classification": classify_fills(
            product, trades, rows_by_key
        ),
    }
    if product == "ASH_COATED_OSMIUM":
        result["matched_flow_pct"] = 100 * min(buy_volume, sell_volume) / max(
            buy_volume, sell_volume
        )
    else:
        result["time_at_or_above_60_pct"] = 100 * sum(
            value >= 60 for value in position_path
        ) / len(position_path)
        result["time_between_70_and_80_pct"] = 100 * sum(
            70 <= value <= 80 for value in position_path
        ) / len(position_path)
    return result


def load_trader() -> object:
    module = types.ModuleType("datamodel")
    module.Order = Order
    module.OrderDepth = OrderDepth
    module.TradingState = TradingState
    sys.modules["datamodel"] = module
    spec = importlib.util.spec_from_file_location(
        "round_two_trader", ROUND_DIR / "trader.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Round 2 trader")
    trader_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trader_module)
    return trader_module.Trader()


def debug_states(log_entries: list[dict[str, object]]) -> dict[int, dict[str, object]]:
    pattern = re.compile(
        r"STATE\|pos=(-?\d+) ref=([-0-9.]+) fair=([-0-9.]+) "
        r"bid=(-?\d+)x(\d+) ask=(-?\d+)x(\d+) spread=(\d+)"
    )
    output = {}
    for entry in log_entries:
        lambda_log = str(entry.get("lambdaLog", ""))
        match = pattern.search(lambda_log)
        if match is None:
            continue
        quote_match = re.search(
            r"QUOTE\|.*chosen_buy=(.*?) chosen_sell=([^\n]+)", lambda_log
        )
        output[int(entry["timestamp"])] = {
            "position": int(match.group(1)),
            "reference": float(match.group(2)),
            "fair": float(match.group(3)),
            "best_bid": int(match.group(4)),
            "bid_volume": int(match.group(5)),
            "best_ask": int(match.group(6)),
            "ask_volume": int(match.group(7)),
            "spread": int(match.group(8)),
            "chosen_buy": quote_match.group(1) if quote_match else "",
            "chosen_sell": quote_match.group(2) if quote_match else "",
        }
    return output


def replay_top_three_snapshots(
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    position_before: dict[int, dict[str, int]],
    ending_positions: dict[str, int],
    log_entries: list[dict[str, object]],
) -> dict[str, object]:
    trader = load_trader()
    trader_data = ""
    order_counts = Counter()
    snapshots_with_orders = Counter()
    marketable_order_counts = Counter()
    marketable_volume = Counter()
    maximum_order_count = Counter()
    projected_long = defaultdict(lambda: -math.inf)
    projected_short = defaultdict(lambda: math.inf)
    violations = []
    osmium_fairs = {}
    osmium_variances = []
    osmium_gammas = Counter()
    characteristic_shape = 0
    pepper_observations = {}
    logged = debug_states(log_entries)
    replayed_checkpoints = {}

    original_compute_fair = trader._compute_fair_value

    def observed_compute_fair(
        product: str,
        position: int,
        reference_price: float,
        depth: OrderDepth,
        timestamp: int,
    ) -> float:
        fair = original_compute_fair(
            product, position, reference_price, depth, timestamp
        )
        params = trader.PARAMS[product]
        history = list(trader.price_history[product])
        trend = trader.linear_trends[product]
        if len(trend.prices) >= 20:
            base = trend.predict(timestamp + 50)
        else:
            base = sum(history) / len(history)
        deep_obi = trader._deep_order_book_imbalance(depth)
        obi_adjustment = (deep_obi - 0.5) * params["obi_weight"]
        gap = position - params["target_position"]
        multiplier = params["long_gamma_multiplier"]
        if gap < 0:
            multiplier = params["short_gamma_multiplier"]
        inventory_adjustment = -params["gamma"] * multiplier * gap
        short_length = params["short_history"]
        pullback_bonus = 0.0
        if len(history) >= short_length:
            short_mean = sum(history[-short_length:]) / short_length
            if reference_price < short_mean:
                pullback_bonus = (
                    short_mean - reference_price
                ) * params["pullback_weight"]
        slope, _ = trend.get_trend()
        pepper_observations[timestamp] = {
            "reference": reference_price,
            "fair": fair,
            "trend_base": base,
            "trend_slope": slope,
            "deep_obi": deep_obi,
            "obi_adjustment": obi_adjustment,
            "inventory_adjustment": inventory_adjustment,
            "pullback_bonus": pullback_bonus,
        }
        return fair

    trader._compute_fair_value = observed_compute_fair

    with contextlib.redirect_stdout(io.StringIO()):
        for timestamp in range(0, 1_000_000, 100):
            depths = {
                product: order_depth(rows_by_key[(timestamp, product)])
                for product in PRODUCTS
            }
            position = {
                product: position_before[timestamp].get(product, 0)
                for product in PRODUCTS
            }
            state = TradingState(timestamp, trader_data, depths, position)
            orders_by_product, conversions, trader_data = trader.run(state)
            if conversions != 0:
                violations.append(f"nonzero conversions at {timestamp}")

            state_data = json.loads(trader_data) if trader_data else {}
            if "fair_ema" in state_data:
                osmium_fairs[timestamp] = float(state_data["fair_ema"])
                prices = [float(value) for value in state_data.get("prices_osmium", [])]
                if len(prices) < 2:
                    variance = 1.0
                else:
                    variance = max(statistics.variance(prices), 1.0)
                osmium_variances.append(variance)
                absolute_position = abs(position["ASH_COATED_OSMIUM"])
                gamma = 0.004 if absolute_position <= 30 else 0.007
                if absolute_position > 55:
                    gamma = 0.012
                osmium_gammas[str(gamma)] += 1

            osmium_depth = depths["ASH_COATED_OSMIUM"]
            osmium_best_bid = max(osmium_depth.buy_orders)
            osmium_best_ask = min(osmium_depth.sell_orders)
            osmium_bid_volume = osmium_depth.buy_orders[osmium_best_bid]
            osmium_ask_volume = abs(osmium_depth.sell_orders[osmium_best_ask])
            if (
                8 <= osmium_bid_volume <= 16 or 8 <= osmium_ask_volume <= 16
            ) and osmium_best_ask - osmium_best_bid >= 10:
                characteristic_shape += 1

            for product in PRODUCTS:
                orders = orders_by_product.get(product, [])
                depth = depths[product]
                best_bid = max(depth.buy_orders, default=None)
                best_ask = min(depth.sell_orders, default=None)
                order_counts[product] += len(orders)
                maximum_order_count[product] = max(
                    maximum_order_count[product], len(orders)
                )
                if orders:
                    snapshots_with_orders[product] += 1
                buys = [order for order in orders if order.quantity > 0]
                sells = [order for order in orders if order.quantity < 0]
                buy_quantity = sum(order.quantity for order in buys)
                sell_quantity = -sum(order.quantity for order in sells)
                projected_long[product] = max(
                    projected_long[product], position[product] + buy_quantity
                )
                projected_short[product] = min(
                    projected_short[product], position[product] - sell_quantity
                )
                if position[product] + buy_quantity > 80:
                    violations.append(f"long limit {product} at {timestamp}")
                if position[product] - sell_quantity < -80:
                    violations.append(f"short limit {product} at {timestamp}")
                for order in orders:
                    if not isinstance(order.price, int):
                        violations.append(f"noninteger price {product} at {timestamp}")
                    is_marketable = (
                        order.quantity > 0
                        and best_ask is not None
                        and order.price >= best_ask
                    ) or (
                        order.quantity < 0
                        and best_bid is not None
                        and order.price <= best_bid
                    )
                    if is_marketable:
                        marketable_order_counts[product] += 1
                        marketable_volume[product] += abs(order.quantity)

            if timestamp in logged:
                pepper_depth = depths["INTARIAN_PEPPER_ROOT"]
                pepper_orders = orders_by_product["INTARIAN_PEPPER_ROOT"]
                pepper_best_bid = max(pepper_depth.buy_orders)
                pepper_best_ask = min(pepper_depth.sell_orders)
                passive_buys = [
                    order
                    for order in pepper_orders
                    if order.quantity > 0 and order.price < pepper_best_ask
                ]
                passive_sells = [
                    order
                    for order in pepper_orders
                    if order.quantity < 0 and order.price > pepper_best_bid
                ]

                def format_orders(orders: list[Order]) -> str:
                    if not orders:
                        return "-"
                    return ",".join(
                        f"{order.price}x{order.quantity}" for order in orders
                    )

                replayed_checkpoints[timestamp] = {
                    "position": position["INTARIAN_PEPPER_ROOT"],
                    "best_bid": pepper_best_bid,
                    "bid_volume": pepper_depth.buy_orders[pepper_best_bid],
                    "best_ask": pepper_best_ask,
                    "ask_volume": abs(pepper_depth.sell_orders[pepper_best_ask]),
                    "spread": pepper_best_ask - pepper_best_bid,
                    "chosen_buy": format_orders(passive_buys),
                    "chosen_sell": format_orders(passive_sells),
                }

    replay_validation = []
    for timestamp, actual in sorted(logged.items()):
        reconstructed = pepper_observations[timestamp]
        checkpoint = replayed_checkpoints[timestamp]
        replay_validation.append(
            {
                "timestamp": timestamp,
                "reference_absolute_error": abs(
                    reconstructed["reference"] - actual["reference"]
                ),
                "fair_absolute_error": abs(reconstructed["fair"] - actual["fair"]),
                "state_matches": all(
                    checkpoint[key] == actual[key]
                    for key in (
                        "position",
                        "best_bid",
                        "bid_volume",
                        "best_ask",
                        "ask_volume",
                        "spread",
                    )
                ),
                "passive_ladders_match": checkpoint["chosen_buy"]
                == actual["chosen_buy"]
                and checkpoint["chosen_sell"] == actual["chosen_sell"],
            }
        )

    osmium_rows = [
        rows_by_key[(timestamp, "ASH_COATED_OSMIUM")]
        for timestamp in range(0, 1_000_000, 100)
    ]
    fair_mid_gaps = [
        osmium_fairs[int(row["timestamp"])] - float(row["mid_price"])
        for row in osmium_rows
    ]
    pepper_warmed = [
        value
        for timestamp, value in pepper_observations.items()
        if timestamp >= 1_900
    ]
    trend_slopes = [value["trend_slope"] for value in pepper_warmed]
    pullbacks = [value["pullback_bonus"] for value in pepper_warmed]
    return {
        "snapshots_replayed": 10_000,
        "exported_top_three_book_only": True,
        "state_uses_only_prior_timestamp_fills": True,
        "completed_without_exception": True,
        "limit_violations": violations,
        "orders_returned": dict(order_counts),
        "snapshots_with_orders": dict(snapshots_with_orders),
        "maximum_orders_in_one_snapshot": dict(maximum_order_count),
        "marketable_orders": dict(marketable_order_counts),
        "marketable_indicated_volume": dict(marketable_volume),
        "worst_projected_long_position": dict(projected_long),
        "worst_projected_short_position": dict(projected_short),
        "ending_positions_reconstructed": ending_positions,
        "ash_coated_osmium_model": {
            "fair_start": osmium_fairs[0],
            "fair_end": osmium_fairs[999_900],
            "fair_mean": statistics.mean(osmium_fairs.values()),
            "fair_minimum": min(osmium_fairs.values()),
            "fair_maximum": max(osmium_fairs.values()),
            "fair_mid_mean_error": statistics.mean(fair_mid_gaps),
            "fair_mid_median_absolute_error": statistics.median(
                abs(value) for value in fair_mid_gaps
            ),
            "fair_within_five_ticks_pct": 100
            * sum(abs(value) <= 5 for value in fair_mid_gaps)
            / len(fair_mid_gaps),
            "fair_within_ten_ticks_pct": 100
            * sum(abs(value) <= 10 for value in fair_mid_gaps)
            / len(fair_mid_gaps),
            "variance_mean": statistics.mean(osmium_variances),
            "variance_median": statistics.median(osmium_variances),
            "variance_p95": percentile(osmium_variances, 0.95),
            "variance_maximum": max(osmium_variances),
            "gamma_snapshot_counts": dict(osmium_gammas),
            "characteristic_l1_shape_snapshots": characteristic_shape,
            "characteristic_l1_shape_pct": 100 * characteristic_shape / 10_000,
        },
        "intarian_pepper_root_model": {
            "fair_start_after_warmup": pepper_warmed[0]["fair"],
            "fair_end": pepper_observations[999_900]["fair"],
            "fair_mean_after_warmup": statistics.mean(
                value["fair"] for value in pepper_warmed
            ),
            "trend_slope_median": statistics.median(trend_slopes),
            "trend_slope_p10": percentile(trend_slopes, 0.10),
            "trend_slope_p90": percentile(trend_slopes, 0.90),
            "fair_reference_mean_gap": statistics.mean(
                value["fair"] - value["reference"] for value in pepper_warmed
            ),
            "obi_adjustment_mean_absolute": statistics.mean(
                abs(value["obi_adjustment"]) for value in pepper_warmed
            ),
            "inventory_adjustment_mean": statistics.mean(
                value["inventory_adjustment"] for value in pepper_warmed
            ),
            "inventory_adjustment_p90": percentile(
                [value["inventory_adjustment"] for value in pepper_warmed], 0.90
            ),
            "pullback_active_pct": 100
            * sum(value > 0 for value in pullbacks)
            / len(pullbacks),
            "pullback_mean_when_active": statistics.mean(
                value for value in pullbacks if value > 0
            ),
        },
        "live_debug_validation": {
            "checkpoint_count": len(replay_validation),
            "state_matches_at_all_checkpoints": all(
                item["state_matches"] for item in replay_validation
            ),
            "passive_ladders_match_at_all_checkpoints": all(
                item["passive_ladders_match"] for item in replay_validation
            ),
            "maximum_reference_absolute_error": max(
                item["reference_absolute_error"] for item in replay_validation
            ),
            "maximum_fair_absolute_error": max(
                item["fair_absolute_error"] for item in replay_validation
            ),
        },
    }


def product_pnl_windows(
    rows_by_product: dict[str, list[dict[str, str]]],
) -> dict[str, list[float]]:
    output = {}
    for product in PRODUCTS:
        values_by_timestamp = {
            int(row["timestamp"]): float(row["profit_and_loss"])
            for row in rows_by_product[product]
        }
        checkpoints = [0.0] + [
            values_by_timestamp[timestamp]
            for timestamp in range(100_000, 1_000_000, 100_000)
        ] + [values_by_timestamp[999_900]]
        output[product] = [
            checkpoints[index] - checkpoints[index - 1]
            for index in range(1, len(checkpoints))
        ]
    return output


def main() -> int:
    result = json.loads(
        (ROUND_DIR / "capsule" / "result.json").read_text(encoding="utf-8")
    )
    submission_log = json.loads(
        (ROUND_DIR / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    rows = rows_from_semicolon_log(result["activitiesLog"])
    graph_rows = rows_from_semicolon_log(result["graphLog"])
    rows_by_product = defaultdict(list)
    rows_by_key = {}
    for row in rows:
        product = row["product"]
        rows_by_product[product].append(row)
        rows_by_key[(int(row["timestamp"]), product)] = row

    fills = submission_fills(submission_log["tradeHistory"])
    position_before, position_paths, ending_positions = position_state(
        submission_log["tradeHistory"]
    )
    final_product_profit = {
        product: float(rows_by_product[product][-1]["profit_and_loss"])
        for product in PRODUCTS
    }
    windows = product_pnl_windows(rows_by_product)
    replay = replay_top_three_snapshots(
        rows_by_key,
        position_before,
        ending_positions,
        submission_log["logs"],
    )

    osmium_fairs = {}
    trader = load_trader()
    trader_data = ""
    with contextlib.redirect_stdout(io.StringIO()):
        for timestamp in range(0, 1_000_000, 100):
            depths = {
                product: order_depth(rows_by_key[(timestamp, product)])
                for product in PRODUCTS
            }
            state = TradingState(
                timestamp,
                trader_data,
                depths,
                {
                    product: position_before[timestamp].get(product, 0)
                    for product in PRODUCTS
                },
            )
            _, _, trader_data = trader.run(state)
            state_data = json.loads(trader_data)
            osmium_fairs[timestamp] = float(state_data["fair_ema"])
    osmium_edges = []
    for trade in fills["ASH_COATED_OSMIUM"]:
        fair = osmium_fairs[int(trade["timestamp"])]
        if trade.get("buyer") == "SUBMISSION":
            edge = fair - float(trade["price"])
        else:
            edge = float(trade["price"]) - fair
        osmium_edges.extend([edge] * int(trade["quantity"]))

    report = {
        "round": 2,
        "final_score": float(result["profit"]),
        "round_path": pnl_path_stats(graph_rows),
        "all_products_profitable_in_every_100k_window": all(
            value > 0 for values in windows.values() for value in values
        ),
        "product_pnl_by_100k_window": windows,
        "ash_coated_osmium": {
            "final_profit": final_product_profit["ASH_COATED_OSMIUM"],
            "share_of_round_pct": 100
            * final_product_profit["ASH_COATED_OSMIUM"]
            / float(result["profit"]),
            "market": market_summary(rows_by_product["ASH_COATED_OSMIUM"]),
            **fill_summary(
                "ASH_COATED_OSMIUM",
                fills["ASH_COATED_OSMIUM"],
                rows_by_key,
                position_paths["ASH_COATED_OSMIUM"],
            ),
            "volume_weighted_edge_to_replayed_fair": statistics.mean(osmium_edges),
            "positive_edge_volume_pct": 100
            * sum(value > 0 for value in osmium_edges)
            / len(osmium_edges),
        },
        "intarian_pepper_root": {
            "final_profit": final_product_profit["INTARIAN_PEPPER_ROOT"],
            "share_of_round_pct": 100
            * final_product_profit["INTARIAN_PEPPER_ROOT"]
            / float(result["profit"]),
            "market": market_summary(rows_by_product["INTARIAN_PEPPER_ROOT"]),
            **fill_summary(
                "INTARIAN_PEPPER_ROOT",
                fills["INTARIAN_PEPPER_ROOT"],
                rows_by_key,
                position_paths["INTARIAN_PEPPER_ROOT"],
            ),
        },
        "capsule_snapshot_replay": replay,
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
