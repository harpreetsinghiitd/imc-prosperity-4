import json
import math
import statistics
from collections import deque
from datamodel import Order, OrderDepth, TradingState
from typing import Deque, Dict, List, Tuple


def calc_variance(prices) -> float:

    if len(prices) < 2:
        return 1.0
    mean = sum(prices) / len(prices)
    return max(sum((x - mean) ** 2 for x in prices) / (len(prices) - 1), 1.0)


class LinearTrend:
    def __init__(self, window: int):
        self.window = window
        self.prices: Deque[float] = deque(maxlen=window)
        self.times: Deque[float] = deque(maxlen=window)
        self.sum_x = 0.0
        self.sum_y = 0.0
        self.sum_xy = 0.0
        self.sum_xx = 0.0

    def add(self, t: float, y: float):

        if len(self.prices) == self.window:
            old_t = self.times[0]
            old_y = self.prices[0]
            self.sum_x -= old_t
            self.sum_y -= old_y
            self.sum_xy -= old_t * old_y
            self.sum_xx -= old_t * old_t

        self.prices.append(y)
        self.times.append(t)
        self.sum_x += t
        self.sum_y += y
        self.sum_xy += t * y
        self.sum_xx += t * t

    def get_trend(self) -> Tuple[float, float]:

        n = len(self.prices)
        if n < 2:
            return 0.0, self.prices[0] if n == 1 else 0.0

        denominator = n * self.sum_xx - self.sum_x * self.sum_x
        if abs(denominator) < 1e-9:
            return 0.0, self.sum_y / n

        slope = (n * self.sum_xy - self.sum_x * self.sum_y) / denominator
        intercept = (self.sum_y - slope * self.sum_x) / n
        return slope, intercept

    def predict(self, t: float) -> float:

        slope, intercept = self.get_trend()
        return slope * t + intercept


class Trader:
    POSITION_LIMIT = 80

    def bid(self):
        return 110059

    FAIR_ALPHA = 0.01
    FAIR_PRIOR = 10000
    FAIR_MIN = 9000
    FAIR_MAX = 11000
    ANCHOR = 10000

    ANCHOR_WINDOW = 150
    ANCHOR_MIN_SAMPLES = 30
    ANCHOR_DEVIATION_CAP = 10

    POS_AWARE_THRESHOLD = 25
    POS_AWARE_OFFSET = 1

    TWO_LEVEL_INNER_FRAC_NORMAL = 0.5
    TWO_LEVEL_INNER_FRAC_CRUSH = 1.0
    TWO_LEVEL_OUTER_OFFSET_NORMAL = 3
    TWO_LEVEL_OUTER_OFFSET_CRUSH = 3

    BOT_A_VOL_MIN = 8
    BOT_A_VOL_MAX = 16
    BOT_A_MIN_SPREAD = 10

    PENNY_MIN_VOL = 4

    CONDITIONAL_PENNY_POS_MAX = 20
    CONDITIONAL_PENNY_PRICE_CAP = 10001
    CONDITIONAL_PENNY_PRICE_FLOOR = 9999

    ACO_EOD_FLATTEN_TS = 900000
    ACO_EOD_FLATTEN_MIN_POS = 10

    DEBUG_SNAPSHOT_INTERVAL = {
        "INTARIAN_PEPPER_ROOT": 50000,
    }
    DEBUG_SWEEP_QTY_THRESHOLD = {
        "INTARIAN_PEPPER_ROOT": 25,
    }

    PARAMS = {
        "INTARIAN_PEPPER_ROOT": {
            "history": 60,
            "anchor_span": 320,
            "anchor_weight": 0.0,
            "short_history": 5,
            "min_spread_to_make": 2,
            "obi_buy": 0.56,
            "obi_sell": 0.28,
            "obi_weight": 5.0,
            "gamma": 0.15,
            "short_gamma_multiplier": 1.5,
            "long_gamma_multiplier": 0.5,
            "target_position": 80,
            "trend_weight": 0.55,
            "buy_bias": 0.0,
            "sell_bias": 0.0,
            "vol_threshold": 2.5,
            "pullback_weight": 0.8,
            "dip_sweep_trigger": 1.0,
            "deep_dip_trigger": 3.0,
            "cap_offer_premium": 18.0,
            "cap_offer_short_premium": 8.0,
            "cap_offer_obi": 0.32,
            "cap_offer_size": 2,
            "trend_window": 500,
            "quote_fill_base": 0.16,
            "quote_compete_weight": 0.52,
            "quote_pressure_weight": 0.26,
            "quote_queue_penalty": 0.14,
            "quote_min_edge": 0.03,
            "quote_min_score": 0.02,
        },
    }

    def __init__(self):

        self.price_history: Dict[str, Deque[float]] = {
            product: deque(maxlen=params["history"])
            for product, params in self.PARAMS.items()
        }

        self.anchor_ema: Dict[str, float] = {}

        self.linear_trends: Dict[str, LinearTrend] = {
            product: LinearTrend(params["trend_window"])
            for product, params in self.PARAMS.items()
        }

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}

        try:
            td = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            td = {}

        for product, order_depth in state.order_depths.items():
            if product == "ASH_COATED_OSMIUM":
                pos = state.position.get(product, 0)
                result[product] = self._trade_aco(
                    product, order_depth, pos, td, state.timestamp
                )

            elif product == "INTARIAN_PEPPER_ROOT":
                result[product] = self._trade_ipr(product, order_depth, state)

        return result, 0, json.dumps(td)

    def _update_anchor(self, mid: float, td: dict) -> float:

        window = td.get("anchor_window", [])
        window.append(float(mid))
        if len(window) > self.ANCHOR_WINDOW:
            window.pop(0)
        td["anchor_window"] = window

        if len(window) < self.ANCHOR_MIN_SAMPLES:
            anchor = float(self.ANCHOR)
        else:
            raw_mean = sum(window) / len(window)

            anchor = max(
                float(self.ANCHOR) - self.ANCHOR_DEVIATION_CAP,
                min(float(self.ANCHOR) + self.ANCHOR_DEVIATION_CAP, raw_mean),
            )
        td["anchor_dyn"] = anchor
        return anchor

    def _update_fair_ema(
        self, best_bid: int, best_ask: int, anchor: float, td: dict
    ) -> float:

        mid = (best_bid + best_ask) / 2.0
        fair = td.get("fair_ema", self.FAIR_PRIOR)
        fair = self.FAIR_ALPHA * mid + (1.0 - self.FAIR_ALPHA) * fair
        fair = max(self.FAIR_MIN, min(self.FAIR_MAX, fair))
        td["fair_ema"] = fair
        return fair

    def _trade_aco(
        self, product, od: OrderDepth, pos: int, td: dict, timestamp: int = 0
    ) -> List[Order]:
        orders = []
        limit = 80

        sell_orders = sorted(od.sell_orders.items(), key=lambda x: x[0])
        buy_orders = sorted(od.buy_orders.items(), key=lambda x: -x[0])
        if not sell_orders and not buy_orders:
            return orders

        fair = td.get("fair_ema", self.FAIR_PRIOR)

        s_buy_one = fair
        s_sell_one = fair

        if not sell_orders:
            best_bid = buy_orders[0][0]
            sell_qty = limit + pos
            if sell_qty > 0:
                hit_qty = (
                    min(sell_qty, abs(buy_orders[0][1]))
                    if best_bid >= s_sell_one + 1
                    else 0
                )
                if hit_qty > 0:
                    orders.append(Order(product, best_bid, -hit_qty))
                    sell_qty -= hit_qty
                if sell_qty > 0:
                    orders.append(
                        Order(product, int(math.ceil(s_sell_one + 3)), -sell_qty)
                    )
            return orders

        if not buy_orders:
            best_ask = sell_orders[0][0]
            buy_qty = limit - pos
            if buy_qty > 0:
                hit_qty = (
                    min(buy_qty, abs(sell_orders[0][1]))
                    if best_ask <= s_buy_one - 1
                    else 0
                )
                if hit_qty > 0:
                    orders.append(Order(product, best_ask, hit_qty))
                    buy_qty -= hit_qty
                if buy_qty > 0:
                    orders.append(
                        Order(product, int(math.floor(s_buy_one - 3)), buy_qty)
                    )
            return orders

        best_ask, best_ask_vol = sell_orders[0]
        best_bid, best_bid_vol = buy_orders[0]
        best_ask_vol = abs(best_ask_vol)
        best_bid_vol = abs(best_bid_vol)

        mid_for_anchor = (best_bid + best_ask) / 2.0
        anchor_dyn = self._update_anchor(mid_for_anchor, td)
        fair = self._update_fair_ema(best_bid, best_ask, anchor_dyn, td)
        s_buy = fair
        s_sell = fair

        vol_ratio = (
            best_bid_vol / (best_bid_vol + best_ask_vol)
            if (best_bid_vol + best_ask_vol) > 0
            else 0.5
        )
        micro_price = best_ask * vol_ratio + best_bid * (1 - vol_ratio)

        prices_osmium = td.get("prices_osmium", [])
        prices_osmium.append(micro_price)
        if len(prices_osmium) > 20:
            prices_osmium.pop(0)
        td["prices_osmium"] = prices_osmium
        var = calc_variance(prices_osmium)

        abs_pos = abs(pos)
        if abs_pos <= 30:
            gamma = 0.004
        elif abs_pos <= 55:
            gamma = 0.007
        else:
            gamma = 0.012

        base_spread = 1.0
        inv_skew = pos * gamma * var
        r_buy = s_buy - inv_skew
        r_sell = s_sell - inv_skew

        delta = base_spread + (gamma * var)
        delta = min(max(delta, 1.5), 8.0)

        buy_price = math.floor(r_buy - delta / 2.0)
        sell_price = math.ceil(r_sell + delta / 2.0)

        desired_bid = (
            best_bid + 1
            if (best_bid_vol >= self.PENNY_MIN_VOL and best_bid + 1 < r_buy)
            else best_bid
        )
        desired_ask = (
            best_ask - 1
            if (best_ask_vol >= self.PENNY_MIN_VOL and best_ask - 1 > r_sell)
            else best_ask
        )

        desired_buy_price = min(desired_bid, buy_price)
        desired_sell_price = max(desired_ask, sell_price)

        spread_now = best_ask - best_bid
        bot_a_bid_detected = (
            self.BOT_A_VOL_MIN <= best_bid_vol <= self.BOT_A_VOL_MAX
            and spread_now >= self.BOT_A_MIN_SPREAD
        )
        bot_a_ask_detected = (
            self.BOT_A_VOL_MIN <= best_ask_vol <= self.BOT_A_VOL_MAX
            and spread_now >= self.BOT_A_MIN_SPREAD
        )

        if (
            bot_a_bid_detected
            and abs(pos) <= self.CONDITIONAL_PENNY_POS_MAX
            and (best_bid + 1) <= self.CONDITIONAL_PENNY_PRICE_CAP
            and desired_buy_price < best_bid + 1
        ):
            desired_buy_price = best_bid + 1

        if (
            bot_a_ask_detected
            and abs(pos) <= self.CONDITIONAL_PENNY_POS_MAX
            and (best_ask - 1) >= self.CONDITIONAL_PENNY_PRICE_FLOOR
            and desired_sell_price > best_ask - 1
        ):
            desired_sell_price = best_ask - 1

        total_buy_vol = 0
        total_sell_vol = 0

        for ask_price, ask_vol in sell_orders:
            ask_vol = abs(ask_vol)
            if ask_price <= buy_price:
                vol = min(ask_vol, limit - pos - total_buy_vol)
                if vol > 0:
                    orders.append(Order(product, ask_price, vol))
                    total_buy_vol += vol

        for bid_price, bid_vol in buy_orders:
            bid_vol = abs(bid_vol)
            if bid_price >= sell_price:
                vol = min(bid_vol, limit + pos - total_sell_vol)
                if vol > 0:
                    orders.append(Order(product, bid_price, -vol))
                    total_sell_vol += vol

        eod_mode = (
            timestamp >= self.ACO_EOD_FLATTEN_TS
            and abs(pos) > self.ACO_EOD_FLATTEN_MIN_POS
        )
        pa_threshold = 80 if eod_mode else self.POS_AWARE_THRESHOLD

        pos_aware_buy_px = int(math.floor(fair)) - self.POS_AWARE_OFFSET
        pos_aware_sell_px = int(math.ceil(fair)) + self.POS_AWARE_OFFSET
        if abs(pos + total_buy_vol - total_sell_vol) <= pa_threshold:
            for ask_price, ask_vol in sell_orders:
                ask_vol = abs(ask_vol)
                if pos_aware_buy_px >= ask_price > buy_price:
                    vol = min(ask_vol, limit - pos - total_buy_vol)
                    if vol > 0:
                        orders.append(Order(product, ask_price, vol))
                        total_buy_vol += vol
            for bid_price, bid_vol in buy_orders:
                bid_vol = abs(bid_vol)
                if pos_aware_sell_px <= bid_price < sell_price:
                    vol = min(bid_vol, limit + pos - total_sell_vol)
                    if vol > 0:
                        orders.append(Order(product, bid_price, -vol))
                        total_sell_vol += vol

        spread = best_ask - best_bid
        bot_a_detected = (
            self.BOT_A_VOL_MIN <= best_bid_vol <= self.BOT_A_VOL_MAX
            or self.BOT_A_VOL_MIN <= best_ask_vol <= self.BOT_A_VOL_MAX
        ) and spread >= self.BOT_A_MIN_SPREAD

        if bot_a_detected:
            inner_frac = self.TWO_LEVEL_INNER_FRAC_CRUSH
            outer_offset = self.TWO_LEVEL_OUTER_OFFSET_CRUSH
        else:
            inner_frac = self.TWO_LEVEL_INNER_FRAC_NORMAL
            outer_offset = self.TWO_LEVEL_OUTER_OFFSET_NORMAL

        remaining_buy = limit - pos - total_buy_vol
        remaining_sell = limit + pos - total_sell_vol

        if remaining_buy > 0:
            inner_sz = int(remaining_buy * inner_frac)
            outer_sz = remaining_buy - inner_sz
            if inner_sz > 0:
                orders.append(Order(product, int(desired_buy_price), inner_sz))
            if outer_sz > 0:
                outer_px = int(desired_buy_price) - outer_offset
                orders.append(Order(product, outer_px, outer_sz))

        if remaining_sell > 0:
            inner_sz = int(remaining_sell * inner_frac)
            outer_sz = remaining_sell - inner_sz
            if inner_sz > 0:
                orders.append(Order(product, int(desired_sell_price), -inner_sz))
            if outer_sz > 0:
                outer_px = int(desired_sell_price) + outer_offset
                orders.append(Order(product, outer_px, -outer_sz))

        return orders

    def _trade_ipr(
        self, product: str, order_depth: OrderDepth, state: TradingState
    ) -> List[Order]:
        if product not in self.PARAMS:
            return []

        top = self._top_of_book(order_depth, default_spread=2)
        if top is None:
            return []

        best_bid, bid_volume, best_ask, ask_volume = top
        spread = best_ask - best_bid
        reference_price = self._microprice(best_bid, bid_volume, best_ask, ask_volume)
        position = state.position.get(product, 0)

        self.price_history[product].append(reference_price)
        self._update_anchor_ema(product, reference_price)
        self.linear_trends[product].add(state.timestamp, reference_price)

        if len(self.price_history[product]) < 2:
            return []

        volatility = statistics.stdev(self.price_history[product])
        fair_value = self._compute_fair_value(
            product, position, reference_price, order_depth, state.timestamp
        )

        orders = self._build_orders(
            product=product,
            position=position,
            fair_value=fair_value,
            order_depth=order_depth,
            spread=spread,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            volatility=volatility,
            timestamp=state.timestamp,
        )

        self._debug_tick(
            product=product,
            timestamp=state.timestamp,
            position=position,
            reference_price=reference_price,
            fair_value=fair_value,
            order_depth=order_depth,
            best_bid=best_bid,
            best_ask=best_ask,
            bid_volume=bid_volume,
            ask_volume=ask_volume,
            spread=spread,
            volatility=volatility,
            orders=orders,
        )

        return orders

    def _debug_log(self, timestamp: int, product: str, tag: str, message: str) -> None:

        print(f"DBG|t={timestamp}|{product}|{tag}|{message}")

    def _format_orders(self, orders: List[Order]) -> str:
        if not orders:
            return "-"
        return ",".join(f"{order.price}x{order.quantity}" for order in orders)

    def _top_of_book(
        self, order_depth: OrderDepth, default_spread: int
    ) -> Tuple[int, int, int, int] | None:

        has_bids = len(order_depth.buy_orders) > 0
        has_asks = len(order_depth.sell_orders) > 0

        if not has_bids and not has_asks:
            return None

        best_bid = (
            max(order_depth.buy_orders.keys())
            if has_bids
            else min(order_depth.sell_orders.keys()) - default_spread
        )
        best_ask = (
            min(order_depth.sell_orders.keys())
            if has_asks
            else max(order_depth.buy_orders.keys()) + default_spread
        )

        bid_volume = order_depth.buy_orders.get(best_bid, 0)
        ask_volume = abs(order_depth.sell_orders.get(best_ask, 0))

        return best_bid, bid_volume, best_ask, ask_volume

    def _microprice(
        self, best_bid: int, bid_volume: int, best_ask: int, ask_volume: int
    ) -> float:

        total_volume = bid_volume + ask_volume
        if bid_volume <= 0 or ask_volume <= 0 or total_volume <= 0:
            return (best_bid + best_ask) / 2.0
        return ((bid_volume * best_ask) + (ask_volume * best_bid)) / total_volume

    def _deep_order_book_imbalance(self, order_depth: OrderDepth) -> float:

        bid_vol = sum(order_depth.buy_orders.values())
        ask_vol = sum(abs(v) for v in order_depth.sell_orders.values())
        total = bid_vol + ask_vol
        if total <= 0:
            return 0.5
        return bid_vol / total

    def _update_anchor_ema(self, product: str, reference_price: float) -> None:

        params = self.PARAMS[product]
        span = max(2, int(params.get("anchor_span", 240)))
        alpha = 2.0 / (span + 1.0)
        previous = self.anchor_ema.get(product, reference_price)
        self.anchor_ema[product] = previous + alpha * (reference_price - previous)

    def _compute_fair_value(
        self,
        product: str,
        position: int,
        reference_price: float,
        order_depth: OrderDepth,
        timestamp: int,
    ) -> float:

        params = self.PARAMS[product]
        history = list(self.price_history[product])

        linear_trend = self.linear_trends[product]
        if len(linear_trend.prices) >= 20:
            fair_base = linear_trend.predict(timestamp + 50)
        else:
            fair_base = sum(history) / len(history)

        deep_obi = self._deep_order_book_imbalance(order_depth)
        obi_signal = (deep_obi - 0.5) * params["obi_weight"]

        inventory_anchor = params["target_position"]
        inventory_gap = position - inventory_anchor
        gamma_multiplier = params.get("long_gamma_multiplier", 1.0)
        if inventory_gap < 0:
            gamma_multiplier = params.get("short_gamma_multiplier", 1.0)
        inventory_penalty = params["gamma"] * gamma_multiplier * inventory_gap

        fair_value = fair_base + obi_signal - inventory_penalty + params["buy_bias"]

        short_hist_len = params.get("short_history", 5)
        if len(history) >= short_hist_len:
            short_ma = sum(history[-short_hist_len:]) / short_hist_len
            if reference_price < short_ma:
                pullback_bonus = (short_ma - reference_price) * params.get(
                    "pullback_weight", 0.0
                )
                fair_value += pullback_bonus

        return fair_value

    def _quote_fill_probability(
        self,
        product: str,
        side: int,
        price: int,
        best_bid: int,
        best_ask: int,
        bid_volume: int,
        ask_volume: int,
        deep_obi: float,
    ) -> float:

        params = self.PARAMS[product]
        total_l1 = max(1, bid_volume + ask_volume)
        spread = max(1, best_ask - best_bid)
        inside_span = max(1, spread - 1)

        if side > 0:
            competitiveness = 0.0 if spread <= 1 else (price - best_bid) / inside_span
            contra_pressure = 1.0 - deep_obi
            queue_penalty = (bid_volume / total_l1) if price == best_bid else 0.0
        else:
            competitiveness = 0.0 if spread <= 1 else (best_ask - price) / inside_span
            contra_pressure = deep_obi
            queue_penalty = (ask_volume / total_l1) if price == best_ask else 0.0

        fill_prob = (
            params.get("quote_fill_base", 0.14)
            + params.get("quote_compete_weight", 0.5) * competitiveness
            + params.get("quote_pressure_weight", 0.2) * contra_pressure
            - params.get("quote_queue_penalty", 0.15) * queue_penalty
        )
        return min(0.95, max(0.05, fill_prob))

    def _select_passive_quote(
        self,
        product: str,
        side: int,
        fair_value: float,
        position: int,
        best_bid: int,
        best_ask: int,
        bid_volume: int,
        ask_volume: int,
        deep_obi: float,
        allow_improve: bool,
    ) -> Tuple[int, float, float, float] | None:

        params = self.PARAMS[product]
        best_choice: Tuple[int, float, float, float] | None = None
        best_score = float("-inf")

        if side > 0:
            candidates = [best_bid]
            if allow_improve and best_bid + 1 < best_ask:
                candidates.append(best_bid + 1)
        else:
            candidates = [best_ask]
            if allow_improve and best_ask - 1 > best_bid:
                candidates.append(best_ask - 1)

        for price in candidates:
            edge = fair_value - price if side > 0 else price - fair_value
            if edge < params.get("quote_min_edge", 0.05):
                continue

            fill_prob = self._quote_fill_probability(
                product=product,
                side=side,
                price=price,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_volume=bid_volume,
                ask_volume=ask_volume,
                deep_obi=deep_obi,
            )

            score = edge * fill_prob

            if score > best_score:
                best_score = score
                best_choice = (price, score, fill_prob, edge)

        if best_choice is None or best_choice[1] < params.get("quote_min_score", 0.05):
            return None
        return best_choice

    def _build_orders(
        self,
        product: str,
        position: int,
        fair_value: float,
        order_depth: OrderDepth,
        spread: int,
        best_bid: int,
        best_ask: int,
        bid_volume: int,
        ask_volume: int,
        volatility: float,
        timestamp: int,
    ) -> List[Order]:

        params = self.PARAMS[product]
        orders: List[Order] = []

        total_l1 = bid_volume + ask_volume
        l1_obi = bid_volume / total_l1 if total_l1 > 0 else 0.5

        deep_obi = self._deep_order_book_imbalance(order_depth)

        buy_room = max(0, self.POSITION_LIMIT - position)
        sell_room = max(0, self.POSITION_LIMIT + position)

        obi_buy_signal = (
            l1_obi >= params["obi_buy"]
            and best_ask <= fair_value + params["buy_bias"] + 1
        )
        obi_sell_signal = (
            l1_obi <= params["obi_sell"]
            and best_bid >= fair_value + params["sell_bias"] - 1
        )
        short_ma = None
        history = list(self.price_history[product])

        short_hist_len = min(len(history), params.get("short_history", 5))
        short_ma = sum(history[-short_hist_len:]) / short_hist_len

        aggressive_buy = best_ask <= fair_value - 1 or (
            obi_buy_signal and best_ask <= fair_value
        )
        aggressive_sell = position > 0 and (
            best_bid >= fair_value + 10
            or (obi_sell_signal and best_bid >= fair_value + 2)
        )

        dynamic_spread_req = params["min_spread_to_make"]
        if volatility > params.get("vol_threshold", 999):
            dynamic_spread_req += 1

        if aggressive_buy and buy_room > 0:
            if short_ma is not None:
                trend_val = self.linear_trends[product].predict(timestamp)
                dip_reference = max(short_ma, trend_val)
                dip_gap = dip_reference - best_ask
                max_take_price = best_ask

                if dip_gap >= params.get("dip_sweep_trigger", 1.0):
                    max_take_price = max(
                        max_take_price,
                        int(min(fair_value + 1, dip_reference + 1)),
                    )

                if dip_gap >= params.get("deep_dip_trigger", 3.0):
                    max_take_price = max(
                        max_take_price,
                        int(min(fair_value + 2, dip_reference + 2)),
                    )

                sweep_orders, buy_room = self._sweep_asks(
                    product=product,
                    order_depth=order_depth,
                    buy_room=buy_room,
                    max_take_price=max_take_price,
                )
                orders.extend(sweep_orders)
            else:
                take_qty = min(buy_room, ask_volume)
                if take_qty > 0:
                    orders.append(Order(product, best_ask, take_qty))
                    buy_room -= take_qty

        if aggressive_sell and sell_room > 0:
            take_qty = min(sell_room, bid_volume)
            if take_qty > 0:
                orders.append(Order(product, best_bid, -take_qty))
                sell_room -= take_qty

        if spread >= 6:
            penny_bid = best_bid + 3
            penny_ask = best_ask - 3
        elif spread >= dynamic_spread_req:
            penny_bid = best_bid + 1
            penny_ask = best_ask - 1
        else:
            penny_bid = best_bid
            penny_ask = best_ask

        if buy_room > 0:
            max_buy_price = int(fair_value + params["buy_bias"])
            buy_price = min(penny_bid, max_buy_price)
            buy_quote = buy_room

            if buy_quote > 0:
                orders.extend(
                    self._build_ladder(product, int(buy_price), int(buy_quote), 1)
                )

        if sell_room > 0:
            sell_price = None
            sell_quote = 0

            sell_choice = self._select_passive_quote(
                product=product,
                side=-1,
                fair_value=fair_value + params["sell_bias"],
                position=position,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_volume=bid_volume,
                ask_volume=ask_volume,
                deep_obi=deep_obi,
                allow_improve=spread >= dynamic_spread_req,
            )
            if sell_choice is not None:
                sell_price, _, _, _ = sell_choice
                sell_quote = sell_room

            if sell_quote <= 0:
                min_sell_price = int(fair_value + params["sell_bias"])
                sell_price = max(penny_ask, min_sell_price)
                sell_quote = sell_room

            if short_ma is not None and sell_quote > 0 and sell_price is not None:
                anchor_premium = best_bid - fair_value
                weak_book = l1_obi <= params.get("cap_offer_obi", 0.32)
                overextended = (
                    position >= self.POSITION_LIMIT
                    and weak_book
                    and anchor_premium >= params.get("cap_offer_premium", 18.0)
                )
                if overextended:
                    sell_quote = min(sell_quote, params.get("cap_offer_size", 2))
                    sell_price = max(sell_price, best_bid + 1)

            if sell_quote > 0 and sell_price is not None:
                orders.extend(
                    self._build_ladder(product, int(sell_price), int(sell_quote), -1)
                )

        return orders

    def _sweep_asks(
        self,
        product: str,
        order_depth: OrderDepth,
        buy_room: int,
        max_take_price: int,
    ) -> Tuple[List[Order], int]:

        orders: List[Order] = []
        if buy_room <= 0:
            return orders, buy_room

        for price in sorted(order_depth.sell_orders.keys()):
            if price > max_take_price or buy_room <= 0:
                break

            available = abs(order_depth.sell_orders[price])
            take_qty = min(buy_room, available)
            if take_qty <= 0:
                continue

            orders.append(Order(product, int(price), int(take_qty)))
            buy_room -= take_qty

        return orders, buy_room

    def _build_ladder(
        self, product: str, base_price: int, quantity: int, side: int
    ) -> List[Order]:

        if quantity <= 0:
            return []

        if side > 0:
            ladder_weights = [0.5, 0.3, 0.2]
            ladder_offsets = [0, -1, -2]
        else:
            ladder_weights = [0.25, 0.375, 0.375]
            ladder_offsets = [0, 1, 2]

        slices: List[int] = []
        remaining = quantity
        for idx, weight in enumerate(ladder_weights):
            if idx == len(ladder_weights) - 1:
                slice_qty = remaining
            else:
                slice_qty = min(remaining, int(round(quantity * weight)))
            slices.append(max(0, slice_qty))
            remaining -= slices[-1]

        orders: List[Order] = []
        for offset, slice_qty in zip(ladder_offsets, slices):
            if slice_qty <= 0:
                continue
            price = base_price + offset
            signed_qty = slice_qty if side > 0 else -slice_qty
            orders.append(Order(product, int(price), int(signed_qty)))

        return orders

    def _debug_tick(
        self,
        product: str,
        timestamp: int,
        position: int,
        reference_price: float,
        fair_value: float,
        order_depth: OrderDepth,
        best_bid: int,
        best_ask: int,
        bid_volume: int,
        ask_volume: int,
        spread: int,
        volatility: float,
        orders: List[Order],
    ) -> None:

        interval = self.DEBUG_SNAPSHOT_INTERVAL.get(product, 0)
        snapshot = interval > 0 and timestamp % interval == 0

        aggressive_buy_orders = [
            order for order in orders if order.quantity > 0 and order.price >= best_ask
        ]
        aggressive_sell_orders = [
            order for order in orders if order.quantity < 0 and order.price <= best_bid
        ]
        passive_buy_orders = [
            order for order in orders if order.quantity > 0 and order.price < best_ask
        ]
        passive_sell_orders = [
            order for order in orders if order.quantity < 0 and order.price > best_bid
        ]

        aggressive_buy_qty = sum(order.quantity for order in aggressive_buy_orders)
        aggressive_sell_qty = -sum(order.quantity for order in aggressive_sell_orders)
        aggressive_buy_levels = len({order.price for order in aggressive_buy_orders})
        aggressive_sell_levels = len({order.price for order in aggressive_sell_orders})

        sweep_threshold = self.DEBUG_SWEEP_QTY_THRESHOLD.get(product, 10)
        buy_gap = fair_value - best_ask
        sell_gap = best_bid - fair_value
        total_l1 = max(1, bid_volume + ask_volume)
        l1_obi = bid_volume / total_l1
        deep_obi = self._deep_order_book_imbalance(order_depth)
        one_sided = int(not order_depth.buy_orders or not order_depth.sell_orders)

        should_log_state = (
            snapshot
            or aggressive_buy_qty >= sweep_threshold
            or aggressive_sell_qty >= sweep_threshold
            or aggressive_buy_levels > 1
            or aggressive_sell_levels > 1
        )
        if should_log_state:
            self._debug_log(
                timestamp=timestamp,
                product=product,
                tag="STATE",
                message=(
                    f"pos={position} ref={reference_price:.2f} fair={fair_value:.2f} "
                    f"bid={best_bid}x{bid_volume} ask={best_ask}x{ask_volume} "
                    f"spread={spread} vol={volatility:.2f} "
                    f"l1_obi={l1_obi:.3f} deep_obi={deep_obi:.3f} "
                    f"buy_gap={buy_gap:.2f} sell_gap={sell_gap:.2f} one_sided={one_sided}"
                ),
            )

        if snapshot:
            params = self.PARAMS[product]
            dynamic_spread_req = params["min_spread_to_make"]
            if volatility > params.get("vol_threshold", 999):
                dynamic_spread_req += 1
            sell_choice = self._select_passive_quote(
                product=product,
                side=-1,
                fair_value=fair_value + params["sell_bias"],
                position=position,
                best_bid=best_bid,
                best_ask=best_ask,
                bid_volume=bid_volume,
                ask_volume=ask_volume,
                deep_obi=deep_obi,
                allow_improve=spread >= dynamic_spread_req,
            )
            if sell_choice is None:
                pepper_quote = "sell_choice=-"
            else:
                sell_price, score, fill_prob, edge = sell_choice
                pepper_quote = (
                    f"sell_choice={sell_price} score={score:.3f} "
                    f"fill={fill_prob:.3f} edge={edge:.2f}"
                )
            self._debug_log(
                timestamp=timestamp,
                product=product,
                tag="QUOTE",
                message=(
                    f"{pepper_quote} chosen_buy={self._format_orders(passive_buy_orders)} "
                    f"chosen_sell={self._format_orders(passive_sell_orders)}"
                ),
            )

        if (
            aggressive_buy_levels > 1
            or aggressive_sell_levels > 1
            or aggressive_buy_qty >= sweep_threshold
            or aggressive_sell_qty >= sweep_threshold
        ):
            self._debug_log(
                timestamp=timestamp,
                product=product,
                tag="TAKE",
                message=(
                    f"aggr_buy={self._format_orders(aggressive_buy_orders)} "
                    f"aggr_sell={self._format_orders(aggressive_sell_orders)}"
                ),
            )
