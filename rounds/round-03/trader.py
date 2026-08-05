from datamodel import OrderDepth, TradingState, Order
from typing import Dict, List
import json, math


LIMITS = {
    "HYDROGEL_PACK": 200,
    "VELVETFRUIT_EXTRACT": 200,
    "VEV_4000": 300,
    "VEV_4500": 300,
    "VEV_5000": 300,
    "VEV_5100": 300,
    "VEV_5200": 300,
    "VEV_5300": 300,
    "VEV_5400": 300,
    "VEV_5500": 300,
    "VEV_6000": 300,
    "VEV_6500": 300,
}


OPTION_CFG = {
    "VEV_5000": {"delta": 0.6536, "offset": -3176.2, "thr_open": 5.0, "thr_close": 0.0},
    "VEV_5100": {"delta": 0.5774, "offset": -2864.5, "thr_open": 4.0, "thr_close": 0.3},
    "VEV_5200": {"delta": 0.4367, "offset": -2197.1, "thr_open": 3.0, "thr_close": 0.0},
    "VEV_5300": {"delta": 0.2727, "offset": -1385.0, "thr_open": 1.5, "thr_close": 0.0},
    "VEV_5400": {"delta": 0.1289, "offset": -660.6, "thr_open": 2.0, "thr_close": 0.5},
    "VEV_5500": {"delta": 0.0549, "offset": -281.4, "thr_open": 3.0, "thr_close": 0.3},
}


DELTA_EST = {
    "VEV_4000": 1.00,
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

WALLMID_PRODUCTS = ["VEV_4000", "VEV_4500"]
PARITY_ARB_STRIKES = [4500]


HG_OU_FAIR = 9985.0
HG_OU_ENTRY = 40.0
HG_OU_EXIT = 0.0
HG_OU_QTY = 20
HG_OU_POS_CAP = 200
HG_OU_ALPHA = 0.0002


VE_OU_FAIR = 5249.0
VE_OU_ENTRY = 20.0
VE_OU_EXIT = 0.0
VE_OU_QTY = 20
VE_OU_POS_CAP = 100


DELTA_CAP = 1000
DELTA_TARGET = 500
SHORT_CAP = 250
EOR_START = 0.92
BASE_LOT = 25
MIN_LOT = 5
MAX_LOT = 40


def get_book(od):
    bids = {p: abs(v) for p, v in od.buy_orders.items()} if od.buy_orders else {}
    asks = {p: abs(v) for p, v in od.sell_orders.items()} if od.sell_orders else {}
    return bids, asks


def wall_mid(bids, asks):
    if not bids or not asks:
        return None
    return (min(bids) + max(asks)) / 2.0


def best_mid(bids, asks):
    if not bids or not asks:
        return None
    return (max(bids) + min(asks)) / 2.0


class Trader:
    def _eor_scale(self, ts, max_ts=999900):
        start = EOR_START * max_ts
        if ts < start:
            return 1.0
        return max(0.05, (max_ts - ts) / (max_ts - start))

    def _lot_scaled(self, abs_dev, thr_open):

        ratio = abs_dev / max(thr_open, 0.5)
        lot = int(BASE_LOT * ratio)
        return max(MIN_LOT, min(MAX_LOT, lot))

    def _portfolio_delta(self, state):
        total = float(state.position.get("VELVETFRUIT_EXTRACT", 0))
        for sym, delta in DELTA_EST.items():
            total += state.position.get(sym, 0) * delta
        return total

    def ve_ou_trade(self, state):

        orders = []
        od = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if od is None:
            return orders

        bids, asks = get_book(od)
        mid = best_mid(bids, asks)
        if mid is None or not bids or not asks:
            return orders

        best_b = max(bids)
        best_a = min(asks)
        pos = state.position.get("VELVETFRUIT_EXTRACT", 0)
        dev = mid - VE_OU_FAIR

        if dev <= -VE_OU_ENTRY and pos < VE_OU_POS_CAP:
            qty = min(VE_OU_QTY, VE_OU_POS_CAP - pos, asks[best_a])
            if qty > 0:
                orders.append(Order("VELVETFRUIT_EXTRACT", best_a, qty))
        elif dev >= VE_OU_ENTRY and pos > -VE_OU_POS_CAP:
            qty = min(VE_OU_QTY, VE_OU_POS_CAP + pos, bids[best_b])
            if qty > 0:
                orders.append(Order("VELVETFRUIT_EXTRACT", best_b, -qty))
        elif pos > 0 and dev >= -VE_OU_EXIT:
            qty = min(VE_OU_QTY, pos, bids[best_b])
            if qty > 0:
                orders.append(Order("VELVETFRUIT_EXTRACT", best_b, -qty))
        elif pos < 0 and dev <= VE_OU_EXIT:
            qty = min(VE_OU_QTY, -pos, asks[best_a])
            if qty > 0:
                orders.append(Order("VELVETFRUIT_EXTRACT", best_a, qty))

        return orders

    def hydrogel_ou_trade(self, state, hg_fair):

        orders = []
        od = state.order_depths.get("HYDROGEL_PACK")
        if od is None:
            return orders

        bids, asks = get_book(od)
        mid = best_mid(bids, asks)
        if mid is None or not bids or not asks:
            return orders

        best_b = max(bids)
        best_a = min(asks)
        pos = state.position.get("HYDROGEL_PACK", 0)
        dev = mid - hg_fair

        if dev <= -HG_OU_ENTRY and pos < HG_OU_POS_CAP:
            qty = min(HG_OU_QTY, HG_OU_POS_CAP - pos, asks[best_a])
            if qty > 0:
                orders.append(Order("HYDROGEL_PACK", best_a, qty))
        elif dev >= HG_OU_ENTRY and pos > -HG_OU_POS_CAP:
            qty = min(HG_OU_QTY, HG_OU_POS_CAP + pos, bids[best_b])
            if qty > 0:
                orders.append(Order("HYDROGEL_PACK", best_b, -qty))
        elif pos > 0 and dev >= -HG_OU_EXIT:
            qty = min(HG_OU_QTY, pos, bids[best_b])
            if qty > 0:
                orders.append(Order("HYDROGEL_PACK", best_b, -qty))
        elif pos < 0 and dev <= HG_OU_EXIT:
            qty = min(HG_OU_QTY, -pos, asks[best_a])
            if qty > 0:
                orders.append(Order("HYDROGEL_PACK", best_a, qty))

        return orders

    def wallmid_trade(self, state, sym, eor):
        orders = []
        od = state.order_depths.get(sym)
        if od is None:
            return orders

        bids, asks = get_book(od)
        wmid = wall_mid(bids, asks)
        if wmid is None:
            return orders

        pos = state.position.get(sym, 0)
        limit = LIMITS[sym]

        for ap in sorted(asks):
            if ap < wmid and pos < limit:
                qty = min(limit - pos, asks[ap])
                if qty > 0:
                    orders.append(Order(sym, ap, qty))
                    pos += qty
            elif ap <= wmid and pos < 0:
                qty = min(-pos, asks[ap])
                if qty > 0:
                    orders.append(Order(sym, ap, qty))
                    pos += qty

        for bp in sorted(bids, reverse=True):
            if bp > wmid and pos > -limit:
                qty = min(limit + pos, bids[bp])
                if qty > 0:
                    orders.append(Order(sym, bp, -qty))
                    pos -= qty
            elif bp >= wmid and pos > 0:
                qty = min(pos, bids[bp])
                if qty > 0:
                    orders.append(Order(sym, bp, -qty))
                    pos -= qty

        if not bids or not asks:
            return orders

        bid_px = int(min(bids) + 1)
        ask_px = int(max(asks) - 1)

        for bp in sorted(bids, reverse=True):
            if bids[bp] > 1 and bp + 1 < wmid:
                bid_px = max(bid_px, int(bp + 1))
                break
            elif bp < wmid:
                bid_px = max(bid_px, int(bp))
                break

        for ap in sorted(asks):
            if asks[ap] > 1 and ap - 1 > wmid:
                ask_px = min(ask_px, int(ap - 1))
                break
            elif ap > wmid:
                ask_px = min(ask_px, int(ap))
                break

        rem_buy = max(0, int((limit - pos) * eor))
        rem_sell = max(0, int((limit + pos) * eor))
        if rem_buy > 0:
            orders.append(Order(sym, bid_px, rem_buy))
        if rem_sell > 0:
            orders.append(Order(sym, ask_px, -rem_sell))

        return orders

    def option_trade(self, state, sym, S, eor):
        orders = []
        cfg = OPTION_CFG[sym]
        od = state.order_depths.get(sym)
        if od is None:
            return orders

        bids, asks = get_book(od)
        mid = best_mid(bids, asks)
        if mid is None:
            return orders

        best_b = max(bids) if bids else None
        best_a = min(asks) if asks else None
        if best_b is None or best_a is None:
            return orders

        fv = cfg["delta"] * S + cfg["offset"]
        dev = mid - fv
        thr_o = cfg["thr_open"]
        thr_c = cfg["thr_close"]
        pos = state.position.get(sym, 0)
        limit = LIMITS[sym]
        lot = max(1, int(self._lot_scaled(abs(dev), thr_o) * eor))

        if dev < -thr_o and pos < limit:
            qty = min(limit - pos, lot)
            if qty > 0:
                orders.append(Order(sym, best_a, qty))

        if dev >= -thr_c and pos > 0:
            orders.append(Order(sym, best_b, -pos))

        if dev > thr_o and pos > -SHORT_CAP:
            qty = min(SHORT_CAP + pos, lot)
            if qty > 0:
                orders.append(Order(sym, best_b, -qty))

        if dev <= thr_c and pos < 0:
            orders.append(Order(sym, best_a, -pos))

        if eor < 0.3 and abs(pos) > 10:
            if pos > 0:
                orders.append(Order(sym, best_b, -min(pos, lot)))
            elif pos < 0:
                orders.append(Order(sym, best_a, min(-pos, lot)))

        return orders

    def parity_arb(self, state, S):

        for K in PARITY_ARB_STRIKES:
            sym = f"VEV_{K}"
            od = state.order_depths.get(sym)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            fair = S - K
            ba = min(od.sell_orders)
            bb = max(od.buy_orders)
            spread = ba - bb
            thresh = max(2.0, 0.5 * spread)
            cur = state.position.get(sym, 0)
            limit = LIMITS[sym]
            orders = []
            if ba < fair - thresh:
                qty = min(abs(od.sell_orders[ba]), 30, limit - cur)
                if qty > 0:
                    orders.append(Order(sym, ba, qty))
            if bb > fair + thresh:
                qty = min(od.buy_orders[bb], 30, limit + cur)
                if qty > 0:
                    orders.append(Order(sym, bb, -qty))
            if orders:
                yield sym, orders

    def delta_hedge(self, state, result):
        port_delta = self._portfolio_delta(state)
        if abs(port_delta) <= DELTA_CAP:
            return

        if port_delta > DELTA_CAP:
            hedge_qty = -int(port_delta - DELTA_TARGET)
        else:
            hedge_qty = -int(port_delta + DELTA_TARGET)

        ve_pos = state.position.get("VELVETFRUIT_EXTRACT", 0)
        if hedge_qty > 0:
            hedge_qty = min(hedge_qty, LIMITS["VELVETFRUIT_EXTRACT"] - ve_pos)
        else:
            hedge_qty = max(hedge_qty, -(LIMITS["VELVETFRUIT_EXTRACT"] + ve_pos))

        if hedge_qty == 0:
            return

        od = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if od is None:
            return
        bids, asks = get_book(od)

        if hedge_qty > 0 and asks:
            best_a = min(asks)
            qty = min(hedge_qty, asks[best_a])
            if qty > 0:
                result.setdefault("VELVETFRUIT_EXTRACT", []).append(
                    Order("VELVETFRUIT_EXTRACT", best_a, qty)
                )
        elif hedge_qty < 0 and bids:
            best_b = max(bids)
            qty = min(-hedge_qty, bids[best_b])
            if qty > 0:
                result.setdefault("VELVETFRUIT_EXTRACT", []).append(
                    Order("VELVETFRUIT_EXTRACT", best_b, -qty)
                )

    def run(self, state: TradingState):
        result: Dict[str, List[Order]] = {}
        conversions: int = 0

        td = {}
        try:
            td = json.loads(state.traderData) if state.traderData else {}
        except Exception:
            td = {}
        hg_fair = td.get("hf", HG_OU_FAIR)

        S = None
        vev_od = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if vev_od:
            bids, asks = get_book(vev_od)
            S = best_mid(bids, asks)

        eor = self._eor_scale(state.timestamp)

        hg_od = state.order_depths.get("HYDROGEL_PACK")
        if hg_od:
            hg_bids, hg_asks = get_book(hg_od)
            hg_mid = best_mid(hg_bids, hg_asks)
            if hg_mid is not None:
                hg_fair = HG_OU_ALPHA * hg_mid + (1 - HG_OU_ALPHA) * hg_fair
        try:
            result["HYDROGEL_PACK"] = self.hydrogel_ou_trade(state, hg_fair)
        except Exception:
            result["HYDROGEL_PACK"] = []

        try:
            result["VELVETFRUIT_EXTRACT"] = self.ve_ou_trade(state)
        except Exception:
            result["VELVETFRUIT_EXTRACT"] = []

        for sym in WALLMID_PRODUCTS:
            try:
                result[sym] = self.wallmid_trade(state, sym, eor)
            except Exception:
                result[sym] = []

        if S is not None and state.timestamp >= 10000:
            for sym in OPTION_CFG:
                try:
                    result[sym] = self.option_trade(state, sym, S, eor)
                except Exception:
                    result[sym] = []

        if S is not None:
            try:
                for sym, ords in self.parity_arb(state, S):
                    result[sym] = ords
            except Exception:
                pass

        try:
            self.delta_hedge(state, result)
        except Exception:
            pass

        trader_data = json.dumps({"hf": round(hg_fair, 2)})

        return result, conversions, trader_data
