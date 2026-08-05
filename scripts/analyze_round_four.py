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
ROUND_DIR = ROOT / "rounds" / "round-04"
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
ZONE_VOUCHERS = (
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
)
ATM_VOUCHERS = (
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
class Trade:
    symbol: str
    price: float
    quantity: int
    buyer: str
    seller: str
    timestamp: int


@dataclass
class TradingState:
    timestamp: int
    traderData: str
    order_depths: dict[str, OrderDepth]
    position: dict[str, int]
    market_trades: dict[str, list[Trade]]
    own_trades: dict[str, list[Trade]]


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


def best_mid(depth: OrderDepth) -> float:
    return (max(depth.buy_orders) + min(depth.sell_orders)) / 2


def stable_mid(depth: OrderDepth) -> float:
    return (min(depth.buy_orders) + max(depth.sell_orders)) / 2


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
    mean_x = statistics.mean(xs)
    mean_y = statistics.mean(ys)
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
        "rmse": math.sqrt(sum(value**2 for value in residuals) / len(xs)),
    }


def market_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    valid = [
        row
        for row in rows
        if float(row["mid_price"]) > 0
        and levels(row, "bid")
        and levels(row, "ask")
    ]
    midpoints = [float(row["mid_price"]) for row in valid]
    spreads = [
        levels(row, "ask")[0][0] - levels(row, "bid")[0][0]
        for row in valid
    ]
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
    }


def graph_summary(
    rows: list[dict[str, str]], final_score: float
) -> dict[str, object]:
    timestamps = [float(row["timestamp"]) for row in rows]
    values = [float(row["value"]) for row in rows]
    fit = linear_fit(timestamps, values)
    minimum_index = min(range(len(values)), key=values.__getitem__)
    maximum_index = max(range(len(values)), key=values.__getitem__)
    checkpoints = {}
    for timestamp in (300_000, 400_000, 500_000, 700_000, 900_000):
        index = min(
            range(len(timestamps)),
            key=lambda item: abs(timestamps[item] - timestamp),
        )
        checkpoints[str(timestamp)] = values[index]
    return {
        "sample_count": len(rows),
        "slope_per_100k": fit["slope"] * 100_000,
        "r_squared": fit["r_squared"],
        "minimum": {
            "timestamp": int(timestamps[minimum_index]),
            "value": values[minimum_index],
        },
        "maximum": {
            "timestamp": int(timestamps[maximum_index]),
            "value": values[maximum_index],
        },
        "final_score_as_pct_of_sampled_peak": 100
        * final_score
        / values[maximum_index],
        "checkpoints": checkpoints,
    }


def activity_path_summary(rows: list[dict[str, str]]) -> dict[str, object]:
    values_by_timestamp = defaultdict(float)
    for row in rows:
        values_by_timestamp[int(row["timestamp"])] += float(row["profit_and_loss"])
    timestamps = sorted(values_by_timestamp)
    endpoint_timestamps = [0] + [
        100_000 * block - 100 for block in range(1, 11)
    ]
    endpoint_values = [values_by_timestamp[timestamp] for timestamp in endpoint_timestamps]
    block_changes = [
        end - start for start, end in zip(endpoint_values, endpoint_values[1:])
    ]
    return {
        "positive_100k_intervals": sum(value > 0 for value in block_changes),
        "total_100k_intervals": len(block_changes),
        "all_recorded_snapshots_positive_from_300k": all(
            values_by_timestamp[timestamp] > 0
            for timestamp in timestamps
            if timestamp >= 300_000
        ),
        "minimum_after_300k": min(
            values_by_timestamp[timestamp]
            for timestamp in timestamps
            if timestamp >= 300_000
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


def split_trade_tape(
    trades: list[dict[str, object]],
) -> tuple[
    dict[int, dict[str, list[Trade]]],
    dict[int, dict[str, list[Trade]]],
]:
    market = defaultdict(lambda: defaultdict(list))
    own = defaultdict(lambda: defaultdict(list))
    for item in trades:
        trade = Trade(
            symbol=str(item["symbol"]),
            price=float(item["price"]),
            quantity=int(item["quantity"]),
            buyer=str(item.get("buyer") or ""),
            seller=str(item.get("seller") or ""),
            timestamp=int(item["timestamp"]),
        )
        destination = (
            own
            if trade.buyer == "SUBMISSION" or trade.seller == "SUBMISSION"
            else market
        )
        destination[trade.timestamp][trade.symbol].append(trade)
    return market, own


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
        "completed_flat_to_flat_cycles": len(cycle_profits),
        "profitable_flat_to_flat_cycles": sum(value > 0 for value in cycle_profits),
        "completed_cycle_profit": sum(cycle_profits),
        "ending_position": position_path[-1],
        "position_minimum": min(position_path),
        "position_maximum": max(position_path),
        "position_mean": statistics.mean(position_path),
        "mean_absolute_position": statistics.mean(abs(value) for value in position_path),
        "time_at_long_limit_pct": 100
        * sum(value == (200 if product in PRODUCTS[:2] else 300) for value in position_path)
        / len(position_path),
        "time_at_short_limit_pct": 100
        * sum(value == (-200 if product in PRODUCTS[:2] else -300) for value in position_path)
        / len(position_path),
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
    datamodel.Trade = Trade
    datamodel.TradingState = TradingState
    sys.modules["datamodel"] = datamodel
    spec = importlib.util.spec_from_file_location(
        "round_four_trader", ROUND_DIR / "trader.py"
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load Round 4 trader")
    strategy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(strategy)
    return strategy, strategy.Trader()


def forward_signal_summary(
    signals: dict[int, float],
    series: list[float],
) -> dict[str, object]:
    output = {}
    for horizon, label in (
        (10, "1k"),
        (50, "5k"),
        (100, "10k"),
        (500, "50k"),
    ):
        moves = []
        weights = []
        for timestamp, signal in signals.items():
            index = timestamp // 100
            if signal == 0 or index + horizon >= len(series):
                continue
            move = math.copysign(1, signal) * (series[index + horizon] - series[index])
            moves.append(move)
            weights.append(abs(signal))
        output[label] = {
            "eligible_timestamps": len(moves),
            "mean_move_in_signal_direction": statistics.mean(moves),
            "volume_weighted_mean_move": sum(
                move * weight for move, weight in zip(moves, weights)
            )
            / sum(weights),
            "directional_hit_rate_pct": 100 * sum(move > 0 for move in moves) / len(moves),
        }
    return output


def counterparty_summary(
    market_trades: dict[int, dict[str, list[Trade]]],
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    strategy: object,
) -> dict[str, object]:
    hydrogel_signal = defaultdict(float)
    mark67_signal = defaultdict(float)
    mark14_fade_signal = defaultdict(float)
    velvetfruit_signal = defaultdict(float)
    mark38_events = 0
    mark38_volume = 0
    mark38_buyer_events = 0
    mark38_buyer_volume = 0
    mark38_seller_events = 0
    mark38_seller_volume = 0
    mark67_events = 0
    mark67_volume = 0
    mark14_events = 0
    mark14_volume = 0
    crash_sequences = 0
    crash_timestamps = []
    for timestamp, by_product in market_trades.items():
        for trade in by_product.get("HYDROGEL_PACK", []):
            if trade.buyer == "Mark 38":
                hydrogel_signal[timestamp] -= trade.quantity
                mark38_events += 1
                mark38_volume += trade.quantity
                mark38_buyer_events += 1
                mark38_buyer_volume += trade.quantity
            elif trade.seller == "Mark 38":
                hydrogel_signal[timestamp] += trade.quantity
                mark38_events += 1
                mark38_volume += trade.quantity
                mark38_seller_events += 1
                mark38_seller_volume += trade.quantity
        for trade in by_product.get("VELVETFRUIT_EXTRACT", []):
            if trade.seller == "Mark 22" and trade.buyer == "Mark 49":
                crash_sequences += 1
                crash_timestamps.append(timestamp)
            for participant in ("Mark 67", "Mark 14"):
                weight = strategy.VE_CP_WEIGHTS[participant]
                involved = False
                if trade.buyer == participant:
                    velvetfruit_signal[timestamp] += weight * trade.quantity
                    involved = True
                if trade.seller == participant:
                    velvetfruit_signal[timestamp] -= weight * trade.quantity
                    involved = True
                if involved and participant == "Mark 67":
                    mark67_events += 1
                    mark67_volume += trade.quantity
                    if trade.buyer == participant:
                        mark67_signal[timestamp] += trade.quantity
                    if trade.seller == participant:
                        mark67_signal[timestamp] -= trade.quantity
                if involved and participant == "Mark 14":
                    mark14_events += 1
                    mark14_volume += trade.quantity
                    if trade.buyer == participant:
                        mark14_fade_signal[timestamp] -= trade.quantity
                    if trade.seller == participant:
                        mark14_fade_signal[timestamp] += trade.quantity
    hydrogel_series = [
        stable_mid(order_depth(rows_by_key[(timestamp, "HYDROGEL_PACK")]))
        for timestamp in range(0, 1_000_000, 100)
    ]
    velvetfruit_series = [
        best_mid(order_depth(rows_by_key[(timestamp, "VELVETFRUIT_EXTRACT")]))
        for timestamp in range(0, 1_000_000, 100)
    ]
    return {
        "hydrogel_mark_38": {
            "external_trade_events": mark38_events,
            "external_trade_volume": mark38_volume,
            "buyer_events": mark38_buyer_events,
            "buyer_volume": mark38_buyer_volume,
            "seller_events": mark38_seller_events,
            "seller_volume": mark38_seller_volume,
            "active_timestamps": len(hydrogel_signal),
            "forward_move": forward_signal_summary(hydrogel_signal, hydrogel_series),
        },
        "velvetfruit_selected_flow": {
            "mark_67_external_trade_events": mark67_events,
            "mark_67_external_trade_volume": mark67_volume,
            "mark_14_external_trade_events": mark14_events,
            "mark_14_external_trade_volume": mark14_volume,
            "active_timestamps": len(velvetfruit_signal),
            "mark_67_follow_forward_move": forward_signal_summary(
                mark67_signal, velvetfruit_series
            ),
            "mark_14_fade_forward_move": forward_signal_summary(
                mark14_fade_signal, velvetfruit_series
            ),
            "forward_move": forward_signal_summary(
                velvetfruit_signal, velvetfruit_series
            ),
        },
        "mark_22_to_mark_49_crash_gate": {
            "trigger_count": crash_sequences,
            "trigger_timestamps": crash_timestamps,
            "forward_move": forward_signal_summary(
                {timestamp: -1 for timestamp in crash_timestamps},
                velvetfruit_series,
            ),
        },
    }


def reversion_diagnostics(
    midpoints: list[float], fairs: list[float], threshold: float
) -> dict[str, object]:
    deviations = [midpoint - fair for midpoint, fair in zip(midpoints, fairs)]
    output = {}
    for horizon, label in ((100, "10k"), (500, "50k")):
        moves = []
        for index, deviation in enumerate(deviations[:-horizon]):
            if abs(deviation) < threshold:
                continue
            direction = -math.copysign(1, deviation)
            moves.append(direction * (midpoints[index + horizon] - midpoints[index]))
        output[label] = {
            "eligible_observations": len(moves),
            "mean_move_toward_fair": statistics.mean(moves),
            "move_toward_fair_pct": 100 * sum(value > 0 for value in moves) / len(moves),
        }
    return output


def replay_decisions(
    rows_by_key: dict[tuple[int, str], dict[str, str]],
    position_before: dict[int, dict[str, int]],
    position_paths: dict[str, list[int]],
    fills: dict[str, list[dict[str, object]]],
    market_trades: dict[int, dict[str, list[Trade]]],
    own_trades: dict[int, dict[str, list[Trade]]],
) -> dict[str, object]:
    strategy, trader = load_strategy()
    trader_data = ""
    order_counts = Counter()
    order_volume = Counter()
    marketable_orders = Counter()
    passive_orders = Counter()
    active_snapshots = Counter()
    projected_limit_violations = Counter()
    one_sided_limit_violations = Counter()
    fill_events_reproduced = 0
    fill_volume_reproduced = 0
    total_fill_events = 0
    total_fill_volume = 0
    fills_by_key = defaultdict(list)
    for product, product_fills in fills.items():
        for trade in product_fills:
            fills_by_key[(int(trade["timestamp"]), product)].append(trade)
            total_fill_events += 1
            total_fill_volume += int(trade["quantity"])

    hydrogel_top = []
    hydrogel_stable = []
    hydrogel_fair = []
    hydrogel_base_fair = []
    hydrogel_flow_adjustment = []
    hydrogel_aggressive_state = []
    hydrogel_mm_snapshots = 0
    hydrogel_directional_snapshots = 0
    velvetfruit_spot = []
    velvetfruit_base_center = []
    velvetfruit_center = []
    velvetfruit_flow_adjustment = []
    sigma_path = []
    iv_count_path = []
    iv_dispersion_path = []
    trend_path = []
    crash_path = []
    zone_counts = Counter()
    zone_transitions = 0
    previous_zone = None
    rejection_counts = defaultdict(Counter)
    noninteger_price_count = 0

    for timestamp in range(0, 1_000_000, 100):
        depths = {
            product: order_depth(rows_by_key[(timestamp, product)])
            for product in PRODUCTS
        }
        position = {
            product: position_before[timestamp].get(product, 0)
            for product in PRODUCTS
        }
        state = TradingState(
            timestamp=timestamp,
            traderData=trader_data,
            order_depths=depths,
            position=position,
            market_trades=dict(market_trades.get(timestamp, {})),
            own_trades=dict(own_trades.get(timestamp, {})),
        )
        orders_by_product, conversions, trader_data = trader.run(state)
        if conversions != 0:
            raise AssertionError("Round 4 replay returned a nonzero conversion")
        saved = json.loads(trader_data)

        hg_top = best_mid(depths["HYDROGEL_PACK"])
        hg_stable = stable_mid(depths["HYDROGEL_PACK"])
        hg_base = float(saved["hg"])
        hg_adjustment = strategy.M38_SCALE * float(saved["m38"])
        hydrogel_top.append(hg_top)
        hydrogel_stable.append(hg_stable)
        hydrogel_base_fair.append(hg_base)
        hydrogel_flow_adjustment.append(hg_adjustment)
        hydrogel_fair.append(hg_base + hg_adjustment)
        aggressive = int(saved["al"]) + int(saved["as"])
        hydrogel_aggressive_state.append(aggressive)
        if aggressive:
            hydrogel_directional_snapshots += 1
        else:
            hydrogel_mm_snapshots += 1

        spot = best_mid(depths["VELVETFRUIT_EXTRACT"])
        center_base = float(saved["ve"])
        center_adjustment = strategy.VE_CP_SCALE * float(saved["vcp"])
        center = center_base + center_adjustment
        velvetfruit_spot.append(spot)
        velvetfruit_base_center.append(center_base)
        velvetfruit_flow_adjustment.append(center_adjustment)
        velvetfruit_center.append(center)
        sigma = float(saved["sig"])
        sigma_path.append(sigma)
        trend_up = int(saved["tc"]) >= strategy.TREND_TICKS
        trend_path.append(trend_up)
        crash_suppress = int(saved["ccd"]) > 0
        crash_path.append(crash_suppress)

        tte_start = 4 / 252
        tte_end = 3 / 252
        fraction = timestamp / 999_900 if timestamp < 999_900 else 1
        tte = tte_start + fraction * (tte_end - tte_start)
        valid_ivs = []
        for product in ATM_VOUCHERS:
            midpoint = best_mid(depths[product])
            iv = strategy.bs_iv(
                midpoint, spot, strategy.STRIKES[product], tte
            )
            if iv and 0.05 < iv < 2.0:
                valid_ivs.append(iv)
        iv_count_path.append(len(valid_ivs))
        if len(valid_ivs) >= 2:
            iv_dispersion_path.append(statistics.pstdev(valid_ivs))

        buy_below = center - strategy.ZONE_OFF
        sell_above = center + (
            strategy.ZONE_OFF_TREND if trend_up else strategy.ZONE_OFF
        )
        if spot < buy_below:
            raw_zone = "long"
        elif spot > sell_above:
            raw_zone = "short"
        elif center - strategy.FLAT_OFF <= spot <= center + strategy.FLAT_OFF:
            raw_zone = "flat"
        else:
            raw_zone = "wait"
        zone = "suppressed_long" if crash_suppress and raw_zone == "long" else raw_zone
        zone_counts[zone] += 1
        if previous_zone is not None and zone != previous_zone:
            zone_transitions += 1
        previous_zone = zone

        if zone in ("long", "short"):
            for product in ZONE_VOUCHERS:
                midpoint = best_mid(depths[product])
                fair = strategy.bs_call(
                    spot, strategy.STRIKES[product], tte, sigma
                )
                mispricing = midpoint - fair
                direction = zone
                rejection_counts[product][f"{direction}_candidates"] += 1
                target = 300 if zone == "long" else -300
                if position[product] != target:
                    rejection_counts[product][f"{direction}_action_candidates"] += 1
                rejected = (
                    zone == "long" and mispricing > strategy.BS_REJECT
                ) or (
                    zone == "short" and mispricing < -strategy.BS_REJECT
                )
                if rejected:
                    rejection_counts[product][f"{direction}_rejected"] += 1
                    if position[product] != target:
                        rejection_counts[product][f"{direction}_action_rejected"] += 1

        for product in PRODUCTS:
            orders = orders_by_product.get(product, [])
            if orders:
                active_snapshots[product] += 1
            order_counts[product] += len(orders)
            order_volume[product] += sum(abs(order.quantity) for order in orders)
            projected = position[product] + sum(order.quantity for order in orders)
            if abs(projected) > strategy.LIMITS[product]:
                projected_limit_violations[product] += 1
            buy_projection = position[product] + sum(
                max(order.quantity, 0) for order in orders
            )
            sell_projection = position[product] + sum(
                min(order.quantity, 0) for order in orders
            )
            if (
                buy_projection > strategy.LIMITS[product]
                or sell_projection < -strategy.LIMITS[product]
            ):
                one_sided_limit_violations[product] += 1
            depth = depths[product]
            best_bid = max(depth.buy_orders)
            best_ask = min(depth.sell_orders)
            available = Counter()
            for order in orders:
                if not isinstance(order.price, int):
                    noninteger_price_count += 1
                side = 1 if order.quantity > 0 else -1
                available[(int(order.price), side)] += abs(int(order.quantity))
                marketable = (
                    order.quantity > 0 and order.price >= best_ask
                ) or (
                    order.quantity < 0 and order.price <= best_bid
                )
                if marketable:
                    marketable_orders[product] += 1
                else:
                    passive_orders[product] += 1
            for trade in fills_by_key[(timestamp, product)]:
                side = 1 if trade.get("buyer") == "SUBMISSION" else -1
                key = (int(float(trade["price"])), side)
                quantity = int(trade["quantity"])
                matched = min(quantity, available[key])
                fill_volume_reproduced += matched
                if matched == quantity:
                    fill_events_reproduced += 1
                available[key] -= matched

    stable_changes = [
        abs(hydrogel_stable[index] - hydrogel_stable[index - 1])
        for index in range(1, len(hydrogel_stable))
    ]
    top_changes = [
        abs(hydrogel_top[index] - hydrogel_top[index - 1])
        for index in range(1, len(hydrogel_top))
    ]
    stable_mean = statistics.mean(hydrogel_stable)
    top_mean = statistics.mean(hydrogel_top)
    stable_variance = sum(
        (value - stable_mean) ** 2 for value in hydrogel_stable
    )
    top_variance = sum((value - top_mean) ** 2 for value in hydrogel_top)
    stable_top_correlation = sum(
        (stable_value - stable_mean) * (top_value - top_mean)
        for stable_value, top_value in zip(hydrogel_stable, hydrogel_top)
    ) / math.sqrt(stable_variance * top_variance)
    recorded_limit_violations = {
        product: sum(abs(value) > strategy.LIMITS[product] for value in path)
        for product, path in position_paths.items()
        if any(abs(value) > strategy.LIMITS[product] for value in path)
    }
    voucher_filters = {}
    for product in ZONE_VOUCHERS:
        counts = rejection_counts[product]
        candidates = counts["long_candidates"] + counts["short_candidates"]
        rejected = counts["long_rejected"] + counts["short_rejected"]
        action_candidates = (
            counts["long_action_candidates"]
            + counts["short_action_candidates"]
        )
        action_rejected = (
            counts["long_action_rejected"] + counts["short_action_rejected"]
        )
        voucher_filters[product] = {
            **dict(counts),
            "directional_candidates": candidates,
            "rejected_candidates": rejected,
            "rejection_rate_pct": 100 * rejected / candidates,
            "action_candidates": action_candidates,
            "action_rejected": action_rejected,
            "action_rejection_rate_pct": (
                100 * action_rejected / action_candidates if action_candidates else 0
            ),
        }
    return {
        "snapshots_replayed": 10_000,
        "exported_book_depth": "up to three levels per side",
        "external_trade_routing": "same-timestamp non-SUBMISSION tape",
        "run_returned_on_all_snapshots": True,
        "noninteger_price_count": noninteger_price_count,
        "recorded_position_limit_violations": recorded_limit_violations,
        "net_order_projection_violation_snapshots": dict(projected_limit_violations),
        "one_sided_order_projection_violation_snapshots": dict(
            one_sided_limit_violations
        ),
        "orders_returned": dict(order_counts),
        "order_indicated_volume": dict(order_volume),
        "active_order_snapshots": dict(active_snapshots),
        "marketable_orders": dict(marketable_orders),
        "passive_orders": dict(passive_orders),
        "exported_state_fill_match": {
            "total_fill_events": total_fill_events,
            "same_timestamp_side_price_capacity_events": fill_events_reproduced,
            "event_coverage_pct": 100 * fill_events_reproduced / total_fill_events,
            "total_fill_volume": total_fill_volume,
            "same_timestamp_side_price_capacity_volume": fill_volume_reproduced,
            "volume_coverage_pct": 100 * fill_volume_reproduced / total_fill_volume,
        },
        "hydrogel_model": {
            "stable_midpoint_start": hydrogel_stable[0],
            "stable_midpoint_end": hydrogel_stable[-1],
            "base_ema_start": hydrogel_base_fair[0],
            "base_ema_end": hydrogel_base_fair[-1],
            "adjusted_fair_minimum": min(hydrogel_fair),
            "adjusted_fair_maximum": max(hydrogel_fair),
            "mean_absolute_flow_adjustment": statistics.mean(
                abs(value) for value in hydrogel_flow_adjustment
            ),
            "maximum_absolute_flow_adjustment": max(
                abs(value) for value in hydrogel_flow_adjustment
            ),
            "mean_absolute_stable_mid_change": statistics.mean(stable_changes),
            "mean_absolute_top_mid_change": statistics.mean(top_changes),
            "mean_absolute_stable_top_gap": statistics.mean(
                abs(stable_value - top_value)
                for stable_value, top_value in zip(hydrogel_stable, hydrogel_top)
            ),
            "stable_top_correlation": stable_top_correlation,
            "stable_change_reduction_pct": 100
            * (1 - statistics.mean(stable_changes) / statistics.mean(top_changes)),
            "entry_snapshots": sum(
                abs(midpoint - fair) >= strategy.HG_OU_ENTRY
                for midpoint, fair in zip(hydrogel_stable, hydrogel_fair)
            ),
            "directional_inventory_snapshots": hydrogel_directional_snapshots,
            "market_making_eligible_snapshots": hydrogel_mm_snapshots,
            "maximum_tracked_aggressive_inventory": max(hydrogel_aggressive_state),
            "ema_half_life_observations": math.log(0.5)
            / math.log(1 - strategy.HG_EMA_ALPHA),
            "forward_reversion": reversion_diagnostics(
                hydrogel_stable, hydrogel_fair, strategy.HG_OU_ENTRY
            ),
        },
        "velvetfruit_regime": {
            "base_ema_start": velvetfruit_base_center[0],
            "base_ema_end": velvetfruit_base_center[-1],
            "adjusted_center_minimum": min(velvetfruit_center),
            "adjusted_center_maximum": max(velvetfruit_center),
            "mean_absolute_flow_adjustment": statistics.mean(
                abs(value) for value in velvetfruit_flow_adjustment
            ),
            "maximum_absolute_flow_adjustment": max(
                abs(value) for value in velvetfruit_flow_adjustment
            ),
            "zone_snapshots": dict(zone_counts),
            "zone_transitions": zone_transitions,
            "trend_up_snapshots": sum(trend_path),
            "crash_suppression_snapshots": sum(crash_path),
            "ema_half_life_observations": math.log(0.5)
            / math.log(1 - strategy.VE_EMA_ALPHA),
        },
        "cross_strike_volatility": {
            "sigma_start": sigma_path[0],
            "sigma_initialization": 0.30,
            "sigma_end": sigma_path[-1],
            "sigma_minimum": min(sigma_path),
            "sigma_maximum": max(sigma_path),
            "sigma_mean": statistics.mean(sigma_path),
            "sigma_p10": percentile(sigma_path, 0.10),
            "sigma_p90": percentile(sigma_path, 0.90),
            "mean_valid_iv_inputs_per_snapshot": statistics.mean(iv_count_path),
            "all_six_valid_snapshots": sum(value == 6 for value in iv_count_path),
            "at_least_one_valid_snapshot": sum(value > 0 for value in iv_count_path),
            "mean_cross_strike_iv_dispersion": statistics.mean(iv_dispersion_path),
            "median_cross_strike_iv_dispersion": statistics.median(iv_dispersion_path),
            "iv_dispersion_snapshot_count": len(iv_dispersion_path),
            "ema_half_life_observations": math.log(0.5)
            / math.log(1 - strategy.VOL_ALPHA),
            "voucher_direction_filter": voucher_filters,
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
    market_trades, own_trades = split_trade_tape(submission_log["tradeHistory"])
    position_before, position_paths, ending_positions = position_state(
        submission_log["tradeHistory"]
    )
    product_results = {}
    for product in PRODUCTS:
        product_results[product] = {
            "final_profit": float(rows_by_product[product][-1]["profit_and_loss"]),
            "market": market_summary(rows_by_product[product]),
            **fill_summary(
                product,
                fills[product],
                position_paths[product],
                rows_by_key,
            ),
        }

    profits = {
        product: product_results[product]["final_profit"] for product in PRODUCTS
    }
    active = [product for product in PRODUCTS if fills[product]]
    capsule_positions = {
        str(item["symbol"]): int(item["quantity"])
        for item in result["positions"]
        if str(item["symbol"]) in PRODUCTS
    }
    product_profit_sum = sum(profits.values())
    gross_winners = sum(value for value in profits.values() if value > 0)
    gross_losses = sum(value for value in profits.values() if value < 0)
    report = {
        "round": 4,
        "final_score": float(result["profit"]),
        "improvement_over_round_three": float(result["profit"])
        - float(
            json.loads(
                (ROOT / "rounds" / "round-03" / "summary.json").read_text(
                    encoding="utf-8"
                )
            )["final_score"]
        ),
        "coverage": {
            "activity_rows": len(activity_rows),
            "timestamp_count": len({int(row["timestamp"]) for row in activity_rows}),
            "submission_fill_events": sum(len(fills[product]) for product in PRODUCTS),
            "submission_fill_volume": sum(
                int(trade["quantity"])
                for product in PRODUCTS
                for trade in fills[product]
            ),
            "external_market_trade_events": sum(
                len(product_trades)
                for timestamp_trades in market_trades.values()
                for product_trades in timestamp_trades.values()
            ),
        },
        "products_observed": len(PRODUCTS),
        "active_products": len(active),
        "positive_active_products": sum(profits[product] > 0 for product in active),
        "gross_winner_profit": gross_winners,
        "gross_loss_profit": gross_losses,
        "loss_as_pct_of_gross_winners": 100 * abs(gross_losses) / gross_winners,
        "largest_product_share_of_final_score_pct": 100
        * max(profits.values())
        / float(result["profit"]),
        "round_path": graph_summary(graph_rows, float(result["profit"])),
        "activity_path": activity_path_summary(activity_rows),
        "group_final_profit": {
            "hydrogel": profits["HYDROGEL_PACK"],
            "velvetfruit": profits["VELVETFRUIT_EXTRACT"],
            "wall_mid_vev_4000": profits["VEV_4000"],
            "zone_vouchers_4500_to_5500": sum(
                profits[product] for product in ZONE_VOUCHERS
            ),
            "inactive_far_strikes": sum(profits[product] for product in INACTIVE_PRODUCTS),
        },
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
        "counterparty_tape": counterparty_summary(
            market_trades, rows_by_key, load_strategy()[0]
        ),
        "capsule_snapshot_replay": replay_decisions(
            rows_by_key,
            position_before,
            position_paths,
            fills,
            market_trades,
            own_trades,
        ),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
