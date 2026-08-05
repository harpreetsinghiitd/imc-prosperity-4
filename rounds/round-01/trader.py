import json
import math
from typing import List, Dict, Tuple
from datamodel import OrderDepth, TradingState, Order


POS_LIMIT = 80


_DISREGARD = 1
_JOIN_EDGE = 2
ASH_DEFAULT_EDGE = 7
TAKE_THRESH = 2


POS_SKEW_MILD = 40
POS_SKEW_HEAVY = 60


class Trader:
    PEPPER_STOP_LOSS_DD = 2000
    PEPPER_REENTRY_SLOPE_WINDOW = 2000
    PEPPER_REENTRY_SLOPE_MIN = 0.0005
    PEPPER_REENTRY_WAIT = 2000
    PEPPER_MAX_REENTRIES = 1

    def __init__(self):
        pass

    def run(self, state: TradingState) -> Tuple[Dict[str, List[Order]], int, str]:
        result: Dict[str, List[Order]] = {}
        try:
            td = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            td = {}

        for product in state.order_depths:
            od: OrderDepth = state.order_depths[product]
            pos = state.position.get(product, 0)
            orders = []
            if product == "ASH_COATED_OSMIUM":
                orders = self._trade_aco(product, od, pos, td)
            elif product == "INTARIAN_PEPPER_ROOT":
                orders = self._trade_ipr(product, od, pos, td, state.timestamp)
            result[product] = orders
        return result, 0, json.dumps(td)

    def _fv(self, od: OrderDepth, bids, asks, td):
        if not bids and not asks:
            return td.get("fv")

        bot1_estimates = []
        for p in bids:
            if od.buy_orders[p] >= 20:
                bot1_estimates.append(p + 10.5)
        for p in asks:
            if -od.sell_orders[p] >= 20:
                bot1_estimates.append(p - 10.5)
        bot1_fv = sum(bot1_estimates) / len(bot1_estimates) if bot1_estimates else None

        ref_fv = bot1_fv or td.get("fv")
        if ref_fv is None:
            if bids and asks:
                ref_fv = (bids[0] + asks[0]) / 2
            elif bids:
                ref_fv = bids[0] + 8
            else:
                ref_fv = asks[0] - 8

        estimates = []
        for p in bids:
            v = od.buy_orders[p]
            if 10 <= v <= 15:
                if abs(p - (ref_fv - 8)) <= 3:
                    estimates.append((p + 8, 2.0))
            elif v >= 20:
                estimates.append((p + 10.5, 1.0))

        for p in asks:
            v = -od.sell_orders[p]
            if 10 <= v <= 15:
                if abs(p - (ref_fv + 8)) <= 3:
                    estimates.append((p - 8, 2.0))
            elif v >= 20:
                estimates.append((p - 10.5, 1.0))

        if estimates:
            tw = sum(w for _, w in estimates)
            return sum(e * w for e, w in estimates) / tw
        if bids and asks:
            return (bids[0] + asks[0]) / 2
        if bids:
            return bids[0] + 10.5
        if asks:
            return asks[0] - 10.5
        return td.get("fv")

    def _trade_aco(self, product, od: OrderDepth, pos: int, td: dict) -> List[Order]:
        orders: List[Order] = []
        starting_pos = pos

        bids = sorted(od.buy_orders.keys(), reverse=True) if od.buy_orders else []
        asks = sorted(od.sell_orders.keys()) if od.sell_orders else []

        fv = self._fv(od, bids, asks, td)
        if fv is None:
            return orders

        fv_r = int(round(fv))
        td["fv"] = fv

        buy_ordered = 0
        sell_ordered = 0

        for ap in asks:
            if ap > fv_r - TAKE_THRESH:
                break
            vol = -od.sell_orders[ap]
            can = POS_LIMIT - starting_pos - buy_ordered
            if can <= 0:
                break
            qty = min(vol, can)
            orders.append(Order(product, ap, qty))
            buy_ordered += qty

        for bp in bids:
            if bp < fv_r + TAKE_THRESH:
                break
            vol = od.buy_orders[bp]
            can = POS_LIMIT + starting_pos - sell_ordered
            if can <= 0:
                break
            qty = min(vol, can)
            orders.append(Order(product, bp, -qty))
            sell_ordered += qty

        pos_after_take = starting_pos + buy_ordered - sell_ordered

        if pos_after_take > 0:
            for bp in bids:
                if bp < fv_r:
                    break
                vol = od.buy_orders[bp]
                can_clear = min(
                    vol, pos_after_take, POS_LIMIT + starting_pos - sell_ordered
                )
                if can_clear > 0:
                    orders.append(Order(product, bp, -can_clear))
                    sell_ordered += can_clear
                    pos_after_take -= can_clear

        elif pos_after_take < 0:
            for ap in asks:
                if ap > fv_r:
                    break
                vol = -od.sell_orders[ap]
                can_clear = min(
                    vol, -pos_after_take, POS_LIMIT - starting_pos - buy_ordered
                )
                if can_clear > 0:
                    orders.append(Order(product, ap, can_clear))
                    buy_ordered += can_clear
                    pos_after_take += can_clear

        buy_room = POS_LIMIT - starting_pos - buy_ordered
        sell_room = POS_LIMIT + starting_pos - sell_ordered

        our_bid = fv_r - ASH_DEFAULT_EDGE
        for bp in bids:
            if bp <= fv_r - _DISREGARD:
                if fv_r - bp <= _JOIN_EDGE:
                    our_bid = bp
                else:
                    our_bid = bp + 1
                break

        our_ask = fv_r + ASH_DEFAULT_EDGE
        for ap in asks:
            if ap >= fv_r + _DISREGARD:
                if ap - fv_r <= _JOIN_EDGE:
                    our_ask = ap
                else:
                    our_ask = ap - 1
                break

        our_bid = min(our_bid, fv_r - 1)
        our_ask = max(our_ask, fv_r + 1)
        if our_bid >= our_ask:
            our_bid = fv_r - 1
            our_ask = fv_r + 1

        abs_pos = abs(starting_pos)
        skew_ticks = (
            2 if abs_pos >= POS_SKEW_HEAVY else (1 if abs_pos >= POS_SKEW_MILD else 0)
        )
        if skew_ticks:
            if starting_pos > 0:
                our_bid -= skew_ticks
                our_ask -= skew_ticks
            else:
                our_bid += skew_ticks
                our_ask += skew_ticks

            our_bid = min(our_bid, fv_r - 1)
            our_ask = max(our_ask, fv_r + 1)

        if buy_room > 0:
            orders.append(Order(product, our_bid, buy_room))
        if sell_room > 0:
            orders.append(Order(product, our_ask, -sell_room))

        return orders

    def _trade_ipr(
        self, product: str, od: OrderDepth, pos: int, td: dict, timestamp: int = 0
    ) -> List[Order]:
        orders = []
        MAX_POS = 80

        buy_orders = od.buy_orders
        sell_orders = od.sell_orders

        if not sell_orders and not buy_orders:
            return orders

        sell_list = (
            sorted(sell_orders.items(), key=lambda x: x[0]) if sell_orders else []
        )
        best_bid = max(buy_orders.keys()) if buy_orders else None
        best_ask = sell_list[0][0] if sell_list else None

        if best_bid is not None and best_ask is not None:
            mid = (best_bid + best_ask) / 2.0
        elif best_ask is not None:
            mid = best_ask
        else:
            mid = best_bid

        start_price = td.get("ipr_start", mid)
        if "ipr_start" not in td:
            td["ipr_start"] = mid

        fair = start_price + 0.001 * timestamp

        hist = td.setdefault("ipr_mid_hist", [])
        hist.append([timestamp, float(mid)])
        window = self.PEPPER_REENTRY_SLOPE_WINDOW
        while hist and timestamp - hist[0][0] > window:
            hist.pop(0)

        avg_entry = td.get("ipr_avg_entry")
        total_qty = td.get("ipr_total_qty", 0)
        already_stopped = td.get("ipr_stopped", False)
        stop_count = td.get("ipr_stop_count", 0)
        stopped_ts = td.get("ipr_stopped_ts")

        if already_stopped:
            if pos > 0 and best_bid is not None:
                orders.append(Order(product, int(best_bid), -pos))
                return orders

            if stop_count > self.PEPPER_MAX_REENTRIES:
                return orders

            cond_time = (
                stopped_ts is not None
                and timestamp - stopped_ts >= self.PEPPER_REENTRY_WAIT
            )

            slope = 0.0
            if len(hist) >= 5:
                n_h = len(hist)
                sx = sum(h[0] for h in hist)
                sy = sum(h[1] for h in hist)
                sxx = sum(h[0] * h[0] for h in hist)
                sxy = sum(h[0] * h[1] for h in hist)
                denom = n_h * sxx - sx * sx
                if denom > 0:
                    slope = (n_h * sxy - sx * sy) / denom

            cond_slope = slope > self.PEPPER_REENTRY_SLOPE_MIN

            if cond_time and cond_slope:
                td["ipr_stopped"] = False
                td["ipr_maxed"] = False
            else:
                return orders

        if pos > 0 and avg_entry is not None:
            unreal = pos * (mid - avg_entry)
            if unreal < -self.PEPPER_STOP_LOSS_DD and best_bid is not None:
                orders.append(Order(product, int(best_bid), -pos))
                td["ipr_stopped"] = True
                td["ipr_stopped_ts"] = timestamp
                td["ipr_stop_count"] = stop_count + 1
                td["ipr_avg_entry"] = None
                td["ipr_total_qty"] = 0
                return orders

        was_maxed = td.get("ipr_maxed", False)

        if not was_maxed and sell_list:
            for ask_px, ask_vol_raw in sell_list:
                if pos >= MAX_POS:
                    break
                if ask_px > fair + 10:
                    break
                ask_vol = abs(ask_vol_raw)
                qty = min(MAX_POS - pos, ask_vol)
                if qty <= 0:
                    continue
                orders.append(Order(product, ask_px, qty))
                new_total = total_qty + qty
                if total_qty == 0 or avg_entry is None:
                    new_avg = float(ask_px)
                else:
                    new_avg = (avg_entry * total_qty + ask_px * qty) / new_total
                avg_entry = new_avg
                total_qty = new_total
                td["ipr_avg_entry"] = new_avg
                td["ipr_total_qty"] = new_total
                pos += qty
            if pos >= MAX_POS:
                td["ipr_maxed"] = True

        buy_qty = MAX_POS - pos
        if buy_qty > 0:
            orders.append(Order(product, math.floor(fair), buy_qty))

        return orders
