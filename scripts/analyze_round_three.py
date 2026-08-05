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
ROUND_DIR = ROOT / "rounds" / "round-03"
PRODUCTS = (
    "HYDROGEL_PACK",
    "VELVETFRUIT_EXTRACT",
    "VEV_4000",
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
    "VEV_6000",
    "VEV_6500",
)
CORE_PRODUCTS = ("HYDROGEL_PACK", "VELVETFRUIT_EXTRACT")
WALLMID_PRODUCTS = ("VEV_4000", "VEV_4500")
LINEAR_PRODUCTS = (
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
)
INACTIVE_PRODUCTS = ("VEV_6000", "VEV_6500")


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


def semicolon_rows(value: object) -> list[dict[str, str]]:
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


def linear_fit(xs: list[float], ys: list[float]) -> dict[str, float]:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance_x = sum((value - mean_x) ** 2 for value in xs)
    if variance_x == 0:
        return {
            "slope": 0.0,
            "intercept": mean_y,
            "r_squared": 1.0,
            "rmse": 0.0,
        }
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
    r_squared = 1.0
    if total_variance:
        r_squared = 1 - sum(value**2 for value in residuals) / total_variance
    return {
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "rmse": math.sqrt(sum(value**2 for value in residuals) / count),
    }


def market_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    valid = [
        row
        for row in rows
        if float(row["mid_price"]) > 0
        and levels(row, "bid")
        and levels(row, "ask")
    ]
    timestamps = [float(row["timestamp"]) for row in valid]
    midpoints = [float(row["mid_price"]) for row in valid]
    spreads = [
        levels(row, "ask")[0][0] - levels(row, "bid")[0][0] for row in valid
    ]
    time_fit = linear_fit(timestamps, midpoints)
    return {
        "two_sided_snapshots": len(valid),
        "opening_midpoint": midpoints[0],
        "final_midpoint": midpoints[-1],
        "minimum_midpoint": min(midpoints),
        "maximum_midpoint": max(midpoints),
        "mean_midpoint": statistics.mean(midpoints),
        "midpoint_stdev": statistics.pstdev(midpoints),
        "mean_spread": statistics.mean(spreads),
        "median_spread": statistics.median(spreads),
        "time_slope": time_fit["slope"],
        "time_r_squared": time_fit["r_squared"],
    }


def graph_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    timestamps = [float(row["timestamp"]) for row in rows]
    values = [float(row["value"]) for row in rows]
    fit = linear_fit(timestamps, values)
    increments = [values[index] - values[index - 1] for index in range(1, len(values))]
    minimum_index = min(range(len(values)), key=values.__getitem__)
    maximum_index = max(range(len(values)), key=values.__getitem__)
    return {
        "sample_count": len(rows),
        "slope_per_100k": fit["slope"] * 100_000,
        "r_squared": fit["r_squared"],
        "positive_increments": sum(value > 0 for value in increments),
        "negative_increments": sum(value < 0 for value in increments),
        "minimum": {
            "timestamp": int(timestamps[minimum_index]),
            "value": values[minimum_index],
        },
        "maximum": {
            "timestamp": int(timestamps[maximum_index]),
            "value": values[maximum_index],
        },
    }


def reversion_diagnostics(
    midpoints: list[float], fairs: list[float], threshold: float
) -> dict[str, object]:
    deviations = [
        midpoint - fair for midpoint, fair in zip(midpoints, fairs)
    ]
    output = {}
    for horizon, label in ((100, "10k"), (500, "50k")):
        moves = []
        for index, deviation in enumerate(deviations[:-horizon]):
            if abs(deviation) < threshold:
                continue
            direction = -math.copysign(1, deviation)
            moves.append(
                direction * (midpoints[index + horizon] - midpoints[index])
            )
        output[label] = {
            "eligible_observations": len(moves),
            "mean_move_toward_fair": statistics.mean(moves),
            "move_toward_fair_pct": 100
            * sum(value > 0 for value in moves)
            / len(moves),
        }
    return output


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
        symbol = str(trade["symbol"])
        quantity = int(trade["quantity"])
        if trade.get("buyer") == "SUBMISSION":
            changes[timestamp][symbol] += quantity
        if trade.get("seller") == "SUBMISSION":
            changes[timestamp][symbol] -= quantity

    position = defaultdict(int)
    before = {}
    paths = {product: [] for product in PRODUCTS}
    for timestamp in range(0, 1_000_000, 100):
        before[timestamp] = dict(position)
        for product, change in changes[timestamp].items():
            position[product] += change
        for product in PRODUCTS:
            paths[product].append(position[product])
    return before, paths, dict(position)


def classify_fill(
    product: str,
    trade: dict[str, object],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
) -> str:
    row = rows_by_key[(int(trade["timestamp"]), product)]
    best_bid = levels(row, "bid")[0][0]
    best_ask = levels(row, "ask")[0][0]
    price = float(trade["price"])
    if trade.get("buyer") == "SUBMISSION":
        return "aggressive_buy" if price >= best_ask else "passive_buy"
    return "aggressive_sell" if price <= best_bid else "passive_sell"


def fill_summary(
    product: str,
    trades: list[dict[str, object]],
    position_path: list[int],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
) -> dict[str, object]:
    if not trades:
        return {
            "fill_events": 0,
            "filled_units": 0,
            "buy_events": 0,
            "sell_events": 0,
            "buy_volume": 0,
            "sell_volume": 0,
            "ending_position": position_path[-1],
            "position_minimum": min(position_path),
            "position_maximum": max(position_path),
        }
    buys = [trade for trade in trades if trade.get("buyer") == "SUBMISSION"]
    sells = [trade for trade in trades if trade.get("seller") == "SUBMISSION"]
    buy_volume = sum(int(trade["quantity"]) for trade in buys)
    sell_volume = sum(int(trade["quantity"]) for trade in sells)
    classifications = Counter()
    classification_volume = Counter()
    for trade in trades:
        classification = classify_fill(product, trade, rows_by_key)
        classifications[classification] += 1
        classification_volume[classification] += int(trade["quantity"])
    buy_vwap = (
        sum(float(trade["price"]) * int(trade["quantity"]) for trade in buys)
        / buy_volume
        if buy_volume
        else None
    )
    sell_vwap = (
        sum(float(trade["price"]) * int(trade["quantity"]) for trade in sells)
        / sell_volume
        if sell_volume
        else None
    )
    cycle_position = 0
    cycle_cash = 0.0
    cycle_started = False
    cycle_profits = []
    for trade in sorted(trades, key=lambda item: int(item["timestamp"])):
        quantity = int(trade["quantity"])
        price = float(trade["price"])
        if trade.get("buyer") == "SUBMISSION":
            cycle_position += quantity
            cycle_cash -= price * quantity
        if trade.get("seller") == "SUBMISSION":
            cycle_position -= quantity
            cycle_cash += price * quantity
        cycle_started = cycle_started or cycle_position != 0
        if cycle_started and cycle_position == 0:
            cycle_profits.append(cycle_cash)
            cycle_cash = 0.0
            cycle_started = False
    return {
        "fill_events": len(trades),
        "filled_units": buy_volume + sell_volume,
        "first_fill_timestamp": min(int(trade["timestamp"]) for trade in trades),
        "last_fill_timestamp": max(int(trade["timestamp"]) for trade in trades),
        "buy_events": len(buys),
        "sell_events": len(sells),
        "buy_volume": buy_volume,
        "sell_volume": sell_volume,
        "buy_vwap": buy_vwap,
        "sell_vwap": sell_vwap,
        "vwap_separation": (
            sell_vwap - buy_vwap
            if buy_vwap is not None and sell_vwap is not None
            else None
        ),
        "matched_flow_pct": (
            100 * min(buy_volume, sell_volume) / max(buy_volume, sell_volume)
            if max(buy_volume, sell_volume)
            else None
        ),
        "completed_flat_to_flat_cycles": len(cycle_profits),
        "profitable_flat_to_flat_cycles": sum(
            value > 0 for value in cycle_profits
        ),
        "completed_cycle_profit": sum(cycle_profits),
        "ending_position": position_path[-1],
        "position_minimum": min(position_path),
        "position_maximum": max(position_path),
        "position_mean": statistics.mean(position_path),
        "mean_absolute_position": statistics.mean(
            abs(value) for value in position_path
        ),
        "fill_classification": {
            category: {
                "events": classifications[category],
                "volume": classification_volume[category],
            }
            for category in (
                "aggressive_buy",
                "passive_buy",
                "aggressive_sell",
                "passive_sell",
            )
        },
    }


def load_strategy() -> tuple[object, object]:
    datamodel = types.ModuleType("datamodel")
    datamodel.Order = Order
    datamodel.OrderDepth = OrderDepth
    datamodel.TradingState = TradingState
    sys.modules["datamodel"] = datamodel
    spec = importlib.util.spec_from_file_location(
        "round_three_trader", ROUND_DIR / "trader.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Round 3 trader")
    strategy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(strategy)
    return strategy, strategy.Trader()


def wall_mid_from_depth(depth: OrderDepth) -> float:
    return (min(depth.buy_orders) + max(depth.sell_orders)) / 2


def best_mid_from_depth(depth: OrderDepth) -> float:
    return (max(depth.buy_orders) + min(depth.sell_orders)) / 2


def wall_fill_edge_summary(
    product: str,
    trades: list[dict[str, object]],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
) -> dict[str, float]:
    edges = []
    for trade in trades:
        row = rows_by_key[(int(trade["timestamp"]), product)]
        fair = (
            min(price for price, _ in levels(row, "bid"))
            + max(price for price, _ in levels(row, "ask"))
        ) / 2
        if trade.get("buyer") == "SUBMISSION":
            edge = fair - float(trade["price"])
        else:
            edge = float(trade["price"]) - fair
        edges.extend([edge] * int(trade["quantity"]))
    return {
        "volume_weighted_edge_to_wall_mid": statistics.mean(edges),
        "strictly_positive_edge_volume_pct": 100
        * sum(value > 0 for value in edges)
        / len(edges),
        "nonnegative_edge_volume_pct": 100
        * sum(value >= 0 for value in edges)
        / len(edges),
    }


def replay_decisions(
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    position_before: dict[int, dict[str, int]],
    position_paths: dict[str, list[int]],
    fills: dict[str, list[dict[str, object]]],
) -> dict[str, object]:
    strategy, trader = load_strategy()
    trader_data = ""
    order_counts = Counter()
    snapshots_with_orders = Counter()
    marketable_orders = Counter()
    marketable_volume = Counter()
    passive_orders = Counter()
    maximum_orders = Counter()
    first_order_timestamp = {}
    net_projection_violations = Counter()
    noninteger_price_count = 0
    conversion_total = 0
    hydrogel_fairs = []
    hydrogel_midpoints = []
    hydrogel_deviations = []
    velvetfruit_midpoints = []
    velvetfruit_deviations = []
    portfolio_deltas = []
    end_of_round_scales = []
    parity_signal_count = 0
    option_residuals = {product: [] for product in LINEAR_PRODUCTS}
    option_underlying = {product: [] for product in LINEAR_PRODUCTS}
    option_midpoints = {product: [] for product in LINEAR_PRODUCTS}
    wall_midpoints = {product: [] for product in WALLMID_PRODUCTS}
    top_midpoints = {product: [] for product in WALLMID_PRODUCTS}
    fills_by_key = defaultdict(list)
    total_fill_events = 0
    total_fill_volume = 0
    for product, product_fills in fills.items():
        for trade in product_fills:
            fills_by_key[(int(trade["timestamp"]), product)].append(trade)
            total_fill_events += 1
            total_fill_volume += int(trade["quantity"])
    reproduced_fill_events = 0
    reproduced_fill_volume = 0
    unreproduced_fill_events = 0

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
        underlying_mid = best_mid_from_depth(depths["VELVETFRUIT_EXTRACT"])
        portfolio_deltas.append(trader._portfolio_delta(state))
        end_of_round_scales.append(trader._eor_scale(timestamp))
        velvetfruit_deviations.append(underlying_mid - strategy.VE_OU_FAIR)
        velvetfruit_midpoints.append(underlying_mid)

        for product in WALLMID_PRODUCTS:
            wall_midpoints[product].append(wall_mid_from_depth(depths[product]))
            top_midpoints[product].append(best_mid_from_depth(depths[product]))

        parity_depth = depths["VEV_4500"]
        parity_fair = underlying_mid - 4_500
        best_ask = min(parity_depth.sell_orders)
        best_bid = max(parity_depth.buy_orders)
        parity_threshold = max(2.0, 0.5 * (best_ask - best_bid))
        if (
            best_ask < parity_fair - parity_threshold
            or best_bid > parity_fair + parity_threshold
        ):
            parity_signal_count += 1

        for product in LINEAR_PRODUCTS:
            config = strategy.OPTION_CFG[product]
            midpoint = best_mid_from_depth(depths[product])
            fair = config["delta"] * underlying_mid + config["offset"]
            option_underlying[product].append(underlying_mid)
            option_midpoints[product].append(midpoint)
            option_residuals[product].append(midpoint - fair)

        orders_by_product, conversions, trader_data = trader.run(state)
        conversion_total += conversions
        hydrogel_fair = float(json.loads(trader_data)["hf"])
        hydrogel_mid = best_mid_from_depth(depths["HYDROGEL_PACK"])
        hydrogel_fairs.append(hydrogel_fair)
        hydrogel_midpoints.append(hydrogel_mid)
        hydrogel_deviations.append(hydrogel_mid - hydrogel_fair)

        for product in PRODUCTS:
            orders = orders_by_product.get(product, [])
            depth = depths[product]
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            order_counts[product] += len(orders)
            snapshots_with_orders[product] += int(bool(orders))
            if orders and product not in first_order_timestamp:
                first_order_timestamp[product] = timestamp
            maximum_orders[product] = max(maximum_orders[product], len(orders))
            projected_position = position[product] + sum(
                order.quantity for order in orders
            )
            if abs(projected_position) > strategy.LIMITS[product]:
                net_projection_violations[product] += 1
            for order in orders:
                if not isinstance(order.price, int):
                    noninteger_price_count += 1
                is_marketable = (
                    order.quantity > 0 and order.price >= best_ask
                ) or (order.quantity < 0 and order.price <= best_bid)
                if is_marketable:
                    marketable_orders[product] += 1
                    marketable_volume[product] += abs(order.quantity)
                else:
                    passive_orders[product] += 1

            available = Counter()
            for order in orders:
                side = 1 if order.quantity > 0 else -1
                available[(order.price, side)] += abs(order.quantity)
            for trade in fills_by_key[(timestamp, product)]:
                side = 1 if trade.get("buyer") == "SUBMISSION" else -1
                key = (int(float(trade["price"])), side)
                quantity = int(trade["quantity"])
                if available[key] >= quantity:
                    available[key] -= quantity
                    reproduced_fill_events += 1
                    reproduced_fill_volume += quantity
                else:
                    unreproduced_fill_events += 1

    option_models = {}
    for product in LINEAR_PRODUCTS:
        config = strategy.OPTION_CFG[product]
        observed_fit = linear_fit(
            option_underlying[product], option_midpoints[product]
        )
        rolling_r_squared = []
        for start in range(0, 10_000, 1_000):
            window_fit = linear_fit(
                option_underlying[product][start : start + 1_000],
                option_midpoints[product][start : start + 1_000],
            )
            rolling_r_squared.append(window_fit["r_squared"])
        residuals = option_residuals[product]
        option_models[product] = {
            "configured_delta": config["delta"],
            "configured_offset": config["offset"],
            "open_threshold": config["thr_open"],
            "close_threshold": config["thr_close"],
            "observed_slope": observed_fit["slope"],
            "observed_intercept": observed_fit["intercept"],
            "observed_r_squared": observed_fit["r_squared"],
            "observed_fit_rmse": observed_fit["rmse"],
            "median_100k_window_r_squared": statistics.median(
                rolling_r_squared
            ),
            "model_residual_mean": statistics.mean(residuals),
            "model_residual_stdev": statistics.pstdev(residuals),
            "model_residual_rmse": math.sqrt(
                sum(value**2 for value in residuals) / len(residuals)
            ),
            "model_residual_p10": percentile(residuals, 0.10),
            "model_residual_p90": percentile(residuals, 0.90),
        }

    wall_models = {}
    for product in WALLMID_PRODUCTS:
        walls = wall_midpoints[product]
        tops = top_midpoints[product]
        wall_changes = [
            abs(walls[index] - walls[index - 1])
            for index in range(1, len(walls))
        ]
        top_changes = [
            abs(tops[index] - tops[index - 1])
            for index in range(1, len(tops))
        ]
        strike = int(product.split("_")[1])
        parity_gaps = [
            tops[index]
            - (
                best_mid_from_depth(
                    order_depth(
                        rows_by_key[(index * 100, "VELVETFRUIT_EXTRACT")]
                    )
                )
                - strike
            )
            for index in range(len(tops))
        ]
        intrinsic_values = [
            best_mid_from_depth(
                order_depth(
                    rows_by_key[(index * 100, "VELVETFRUIT_EXTRACT")]
                )
            )
            - strike
            for index in range(len(tops))
        ]
        intrinsic_residuals = [
            top - intrinsic for top, intrinsic in zip(tops, intrinsic_values)
        ]
        top_mean = statistics.mean(tops)
        top_variance = sum((value - top_mean) ** 2 for value in tops)
        wall_intrinsic_gaps = [
            wall - intrinsic
            for wall, intrinsic in zip(walls, intrinsic_values)
        ]
        wall_models[product] = {
            "mean_absolute_wall_top_gap": statistics.mean(
                abs(wall - top) for wall, top in zip(walls, tops)
            ),
            "mean_absolute_wall_change": statistics.mean(wall_changes),
            "mean_absolute_top_mid_change": statistics.mean(top_changes),
            "wall_change_reduction_pct": 100
            * (1 - statistics.mean(wall_changes) / statistics.mean(top_changes)),
            "mean_absolute_parity_gap": statistics.mean(
                abs(value) for value in parity_gaps
            ),
            "intrinsic_identity_r_squared": 1
            - sum(value**2 for value in intrinsic_residuals) / top_variance,
            "intrinsic_identity_rmse": math.sqrt(
                sum(value**2 for value in intrinsic_residuals)
                / len(intrinsic_residuals)
            ),
            "wall_mid_intrinsic_mae": statistics.mean(
                abs(value) for value in wall_intrinsic_gaps
            ),
            "wall_mid_exact_intrinsic_pct": 100
            * sum(value == 0 for value in wall_intrinsic_gaps)
            / len(wall_intrinsic_gaps),
        }

    recorded_limit_violations = {}
    for product, path in position_paths.items():
        count = sum(abs(value) > strategy.LIMITS[product] for value in path)
        if count:
            recorded_limit_violations[product] = count

    return {
        "snapshots_replayed": 10_000,
        "exported_top_three_book_only": True,
        "state_uses_only_prior_timestamp_fills": True,
        "completed_without_exception": True,
        "conversion_total": conversion_total,
        "noninteger_price_count": noninteger_price_count,
        "recorded_position_limit_violations": recorded_limit_violations,
        "net_order_projection_violation_snapshots": dict(
            net_projection_violations
        ),
        "orders_returned": dict(order_counts),
        "snapshots_with_orders": dict(snapshots_with_orders),
        "first_order_timestamp": first_order_timestamp,
        "maximum_orders_in_one_snapshot": dict(maximum_orders),
        "marketable_orders": dict(marketable_orders),
        "marketable_indicated_volume": dict(marketable_volume),
        "passive_orders": dict(passive_orders),
        "recorded_fill_reproduction": {
            "total_fill_events": total_fill_events,
            "reproduced_fill_events": reproduced_fill_events,
            "unreproduced_fill_events": unreproduced_fill_events,
            "total_fill_volume": total_fill_volume,
            "reproduced_fill_volume": reproduced_fill_volume,
            "same_timestamp_side_price_and_capacity_passed": (
                unreproduced_fill_events == 0
                and reproduced_fill_volume == total_fill_volume
            ),
        },
        "hydrogel_model": {
            "fair_start": hydrogel_fairs[0],
            "fair_end": hydrogel_fairs[-1],
            "fair_minimum": min(hydrogel_fairs),
            "fair_maximum": max(hydrogel_fairs),
            "fair_mean": statistics.mean(hydrogel_fairs),
            "deviation_minimum": min(hydrogel_deviations),
            "deviation_maximum": max(hydrogel_deviations),
            "snapshots_at_or_below_long_entry": sum(
                value <= -strategy.HG_OU_ENTRY for value in hydrogel_deviations
            ),
            "snapshots_at_or_above_short_entry": sum(
                value >= strategy.HG_OU_ENTRY for value in hydrogel_deviations
            ),
            "ema_half_life_observations": math.log(0.5)
            / math.log(1 - strategy.HG_OU_ALPHA),
            "forward_reversion": reversion_diagnostics(
                hydrogel_midpoints, hydrogel_fairs, strategy.HG_OU_ENTRY
            ),
        },
        "velvetfruit_model": {
            "fixed_fair": strategy.VE_OU_FAIR,
            "deviation_mean": statistics.mean(velvetfruit_deviations),
            "deviation_minimum": min(velvetfruit_deviations),
            "deviation_maximum": max(velvetfruit_deviations),
            "snapshots_at_or_below_long_entry": sum(
                value <= -strategy.VE_OU_ENTRY
                for value in velvetfruit_deviations
            ),
            "snapshots_at_or_above_short_entry": sum(
                value >= strategy.VE_OU_ENTRY
                for value in velvetfruit_deviations
            ),
            "forward_reversion": reversion_diagnostics(
                velvetfruit_midpoints,
                [strategy.VE_OU_FAIR] * len(velvetfruit_midpoints),
                strategy.VE_OU_ENTRY,
            ),
        },
        "wall_mid_models": wall_models,
        "linear_voucher_models": option_models,
        "portfolio_delta": {
            "minimum": min(portfolio_deltas),
            "maximum": max(portfolio_deltas),
            "mean_absolute": statistics.mean(
                abs(value) for value in portfolio_deltas
            ),
            "absolute_p95": percentile(
                [abs(value) for value in portfolio_deltas], 0.95
            ),
            "final": portfolio_deltas[-1],
            "emergency_cap": strategy.DELTA_CAP,
            "post_hedge_target": strategy.DELTA_TARGET,
            "emergency_trigger_snapshots": sum(
                abs(value) > strategy.DELTA_CAP for value in portfolio_deltas
            ),
        },
        "parity_guard": {
            "product": "VEV_4500",
            "signal_snapshots": parity_signal_count,
        },
        "end_of_round_scaling": {
            "start_fraction": strategy.EOR_START,
            "first_scaled_timestamp": next(
                timestamp
                for timestamp, scale in zip(
                    range(0, 1_000_000, 100), end_of_round_scales
                )
                if scale < 1
            ),
            "minimum_scale": min(end_of_round_scales),
            "snapshots_below_0_3": sum(
                value < 0.3 for value in end_of_round_scales
            ),
        },
        "inactive_products_returned_no_orders": all(
            order_counts[product] == 0 for product in INACTIVE_PRODUCTS
        ),
    }


def main() -> int:
    result = json.loads(
        (ROUND_DIR / "capsule" / "result.json").read_text(encoding="utf-8")
    )
    submission_log = json.loads(
        (ROUND_DIR / "capsule" / "submission.log.json").read_text(encoding="utf-8")
    )
    activity_rows = semicolon_rows(result["activitiesLog"])
    graph_rows = semicolon_rows(result["graphLog"])
    rows_by_product = defaultdict(list)
    rows_by_key = {}
    for row in activity_rows:
        product = row["product"]
        rows_by_product[product].append(row)
        rows_by_key[(int(row["timestamp"]), product)] = row

    fills = submission_fills(submission_log["tradeHistory"])
    position_before, position_paths, ending_positions = position_state(
        submission_log["tradeHistory"]
    )
    product_results = {}
    for product in PRODUCTS:
        product_results[product] = {
            "final_profit": float(
                rows_by_product[product][-1]["profit_and_loss"]
            ),
            "market": market_summary(rows_by_product[product]),
            **fill_summary(
                product,
                fills[product],
                position_paths[product],
                rows_by_key,
            ),
        }
        if product in WALLMID_PRODUCTS:
            product_results[product].update(
                wall_fill_edge_summary(product, fills[product], rows_by_key)
            )

    group_profit = {
        "core_mean_reversion": sum(
            product_results[product]["final_profit"] for product in CORE_PRODUCTS
        ),
        "wall_mid_vouchers": sum(
            product_results[product]["final_profit"]
            for product in WALLMID_PRODUCTS
        ),
        "vev_5000": product_results["VEV_5000"]["final_profit"],
        "remaining_linear_vouchers": sum(
            product_results[product]["final_profit"]
            for product in LINEAR_PRODUCTS
            if product != "VEV_5000"
        ),
        "inactive_far_strikes": sum(
            product_results[product]["final_profit"]
            for product in INACTIVE_PRODUCTS
        ),
    }
    gross_positive_blocks = (
        group_profit["core_mean_reversion"]
        + group_profit["wall_mid_vouchers"]
        + group_profit["vev_5000"]
    )
    capsule_positions = {
        str(item["symbol"]): int(item["quantity"])
        for item in result["positions"]
        if str(item["symbol"]) in PRODUCTS
    }
    product_profit_sum = sum(
        float(product_results[product]["final_profit"])
        for product in PRODUCTS
    )
    report = {
        "round": 3,
        "final_score": float(result["profit"]),
        "coverage": {
            "activity_rows": len(activity_rows),
            "timestamp_count": len(
                {int(row["timestamp"]) for row in activity_rows}
            ),
            "submission_fill_events": sum(
                len(fills[product]) for product in PRODUCTS
            ),
            "submission_fill_volume": sum(
                int(trade["quantity"])
                for product in PRODUCTS
                for trade in fills[product]
            ),
        },
        "products_observed": len(PRODUCTS),
        "products_with_fills": sum(bool(fills[product]) for product in PRODUCTS),
        "round_path": graph_summary(graph_rows),
        "group_final_profit": group_profit,
        "gross_positive_contribution_from_core_wall_and_vev_5000": (
            gross_positive_blocks
        ),
        "product_profit_sum": product_profit_sum,
        "product_profit_sum_matches_final_score": math.isclose(
            product_profit_sum, float(result["profit"]), abs_tol=1e-9
        ),
        "ending_positions_reconstructed": ending_positions,
        "ending_positions_match_capsule": all(
            ending_positions.get(product, 0) == capsule_positions.get(product, 0)
            for product in PRODUCTS
        ),
        "products": product_results,
        "capsule_snapshot_replay": replay_decisions(
            rows_by_key, position_before, position_paths, fills
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
