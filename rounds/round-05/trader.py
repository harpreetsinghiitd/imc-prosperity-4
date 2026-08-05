import json
import math
from typing import Dict, List, Any, Tuple, Optional

try:
    from datamodel import Order, TradingState, OrderDepth
except Exception:

    class Order:
        def __init__(self, symbol, price, quantity):
            self.symbol = symbol
            self.price = int(price)
            self.quantity = int(quantity)

    OrderDepth = Any
    TradingState = Any

P2_PRODUCTS = {
    "TRANSLATOR_ASTRO_BLACK",
}

P2FINAL_ANCHOR_PRODUCTS = ("TRANSLATOR_ECLIPSE_CHARCOAL", "TRANSLATOR_SPACE_GRAY")
SLEEP_POD_PRODUCTS = (
    "SLEEP_POD_COTTON",
    "SLEEP_POD_LAMB_WOOL",
    "SLEEP_POD_NYLON",
    "SLEEP_POD_POLYESTER",
    "SLEEP_POD_SUEDE",
)
SLEEP_PARAMS = {
    "SLEEP_POD_COTTON": (11800.0, 10, 3, 4, 4, 3, 0.55),
    "SLEEP_POD_LAMB_WOOL": (10600.0, 6, -4, 4, 3, 2, 0.50),
    "SLEEP_POD_NYLON": (9900.0, -10, 10, 4, 4, 3, 0.55),
    "SLEEP_POD_POLYESTER": (12500.0, 10, -4, 4, 3, 2, 0.65),
    "SLEEP_POD_SUEDE": (12000.0, 10, 2, 4, 3, 2, 0.65),
}
MICRO_FINAM_PRODUCTS = ("MICROCHIP_OVAL", "MICROCHIP_SQUARE", "MICROCHIP_CIRCLE")
MICRO_FINAM_CORE = ("MICROCHIP_OVAL", "MICROCHIP_SQUARE")
GALAXY_PRODUCTS = (
    "GALAXY_SOUNDS_BLACK_HOLES",
    "GALAXY_SOUNDS_DARK_MATTER",
    "GALAXY_SOUNDS_PLANETARY_RINGS",
    "GALAXY_SOUNDS_SOLAR_FLAMES",
    "GALAXY_SOUNDS_SOLAR_WINDS",
)
GAL_BASE = {
    "GALAXY_SOUNDS_BLACK_HOLES": (12000.0, 10, 4),
    "GALAXY_SOUNDS_DARK_MATTER": (10700.0, 4, -4),
    "GALAXY_SOUNDS_PLANETARY_RINGS": (11300.0, 8, -8),
    "GALAXY_SOUNDS_SOLAR_FLAMES": (11000.0, 6, -6),
    "GALAXY_SOUNDS_SOLAR_WINDS": (9800.0, 8, -8),
}
GAL_PARAMS = {
    "GALAXY_SOUNDS_BLACK_HOLES": (5, 3, 2, 0.55),
    "GALAXY_SOUNDS_DARK_MATTER": (5, 3, 2, 0.65),
    "GALAXY_SOUNDS_PLANETARY_RINGS": (5, 4, 3, 0.55),
    "GALAXY_SOUNDS_SOLAR_FLAMES": (5, 3, 2, 0.65),
    "GALAXY_SOUNDS_SOLAR_WINDS": (5, 4, 3, 0.55),
}


P1_PRODUCTS = {
    "MICROCHIP_RECTANGLE",
    "OXYGEN_SHAKE_CHOCOLATE",
    "PANEL_2X2",
    "PANEL_2X4",
    "ROBOT_DISHES",
    "SNACKPACK_PISTACHIO",
    "TRANSLATOR_VOID_BLUE",
}

P1_PAIRS = [
    ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA", "cv_sum", 0.36),
    ("SNACKPACK_RASPBERRY", "SNACKPACK_STRAWBERRY", "rs_sum", 0.22),
]
P1_MEAN_REVERT = {
    "OXYGEN_SHAKE_CHOCOLATE": (0.22, 10.0),
    "OXYGEN_SHAKE_MORNING_BREATH": (0.28, 8.0),
}

P1_INV_SKEW = {
    "PANEL_2X2": 0.6,
    "ROBOT_DISHES": 0.6,
}
OURS_INV_SKEW = {
    "OXYGEN_SHAKE_MORNING_BREATH": 0.6,
    "OXYGEN_SHAKE_MINT": 0.6,
    "PANEL_1X4": 0.6,
}

IKKK_TRIANGLE_PRODUCTS = ("MICROCHIP_TRIANGLE",)
IKKK_SNACK_PRODUCTS = ("SNACKPACK_CHOCOLATE", "SNACKPACK_VANILLA")
IKKK_SNACK_PARAMS = {
    "SNACKPACK_CHOCOLATE": (200, 125, -10),
    "SNACKPACK_VANILLA": (200, 125, 10),
}

OURS_FADE = [
    "ROBOT_LAUNDRY",
    "SNACKPACK_RASPBERRY",
    "SNACKPACK_STRAWBERRY",
    "SNACKPACK_PISTACHIO",
]

OURS_MM = {
    "OXYGEN_SHAKE_EVENING_BREATH",
    "OXYGEN_SHAKE_GARLIC",
    "OXYGEN_SHAKE_MINT",
    "OXYGEN_SHAKE_MORNING_BREATH",
    "PANEL_1X4",
    "ROBOT_IRONING",
}

PEBBLES_HOLD_SHORT = {"PEBBLES_XS"}
PEBBLES_HOLD_LONG = set()
PEBBLES_MM = set()

PEBBLE_ALL = ["PEBBLES_XS", "PEBBLES_S", "PEBBLES_M", "PEBBLES_L", "PEBBLES_XL"]

PEBBLES_M_FADE_WIN = 800
PEBBLES_M_Z_IN = 1.5

ROBOT_PAIR_WIN = 800
ROBOT_PAIR_Z_IN = 1.5

ROBOT_DECIDE_TICK = 1000
ROBOT_VAC_LEADERS = ["SLEEP_POD_LAMB_WOOL", "PEBBLES_L"]
ROBOT_MOP_LEADERS = ["ROBOT_LAUNDRY", "MICROCHIP_SQUARE", "OXYGEN_SHAKE_MINT"]

REGIME_TARGETS = {
    "ROBOT_VACUUMING": ROBOT_VAC_LEADERS,
    "ROBOT_MOPPING": ROBOT_MOP_LEADERS,
    "PANEL_1X2": [
        "SNACKPACK_CHOCOLATE",
        "OXYGEN_SHAKE_GARLIC",
        "TRANSLATOR_ECLIPSE_CHARCOAL",
        "ROBOT_DISHES",
    ],
    "PANEL_4X4": ["ROBOT_LAUNDRY", "MICROCHIP_SQUARE", "OXYGEN_SHAKE_MINT"],
    "TRANSLATOR_GRAPHITE_MIST": [
        "ROBOT_LAUNDRY",
        "MICROCHIP_SQUARE",
        "OXYGEN_SHAKE_MINT",
    ],
    "PEBBLES_L": ["ROBOT_LAUNDRY", "MICROCHIP_SQUARE", "OXYGEN_SHAKE_MINT"],
    "OXYGEN_SHAKE_EVENING_BREATH": [
        "ROBOT_LAUNDRY",
        "MICROCHIP_SQUARE",
        "OXYGEN_SHAKE_MINT",
    ],
}
REGIME_INVERTED = set()
YES_PEB_DIR_PRODUCTS = ("PEBBLES_XL", "PEBBLES_S")
YES_PEB_DIR_SIZE = {"PEBBLES_XL": 4, "PEBBLES_S": 5}
REGIME_NO_PRE_TRADE = set()

FADE_OVERRIDES = {}

POSITION_LIMIT = 10
ROLL_WIN = 2000
FADE_Z_IN = 1.0
FADE_SIZE = 10
FIRST_500_BLOCK = 500
PEBBLE_BASKET_BETA = 0.18

PANEL_ALL = ["PANEL_1X2", "PANEL_2X2", "PANEL_1X4", "PANEL_2X4", "PANEL_4X4"]
PANEL_ARB = set()
PANEL_BASKET_SUM = 50000.0
PANEL_BETA = 0.18
PANEL_EDGE = 3


def _get_mid(od):
    if not od.buy_orders or not od.sell_orders:
        return 0
    return (max(od.buy_orders) + min(od.sell_orders)) / 2.0


def _get_book(od):
    bb = max(od.buy_orders) if od.buy_orders else None
    ba = min(od.sell_orders) if od.sell_orders else None
    bv = od.buy_orders.get(bb, 0) if bb is not None else 0
    av = -od.sell_orders.get(ba, 0) if ba is not None else 0
    return bb, ba, bv, av


def _welford_update(stats, x):
    stats[0] += 1
    d = x - stats[1]
    stats[1] += d / stats[0]
    stats[2] += d * (x - stats[1])


def _decay_welford(stats, win):
    if stats[0] > win:
        ratio = win / stats[0]
        stats[2] *= ratio
        stats[0] = win


def _welford_std(stats):
    if stats[0] < 2:
        return 0.0
    return math.sqrt(max(0, stats[2] / (stats[0] - 1)))


class Trader:
    def __init__(self):
        self._default_state = {
            "fade": {},
            "prev_mid": {},
            "fade_active": {},
            "mid_hist": {},
            "tick": 0,
            "p2_starts": {},
            "p2_fast": {},
            "p2_slow": {},
            "p1_ema": {},
            "p1_last": {},
            "peb_m_hist": [],
            "robot_spread_hist": [],
            "robot_open_prices": {},
            "robot_vac_signal": None,
            "robot_mop_signal": None,
            "gate_mids": {},
            "avg_cost": {},
            "last_pos": {},
            "stopped": {},
        }

    def run(self, state):
        try:
            S = json.loads(state.traderData) if state.traderData else None
        except Exception:
            S = None
        if not S:
            S = json.loads(json.dumps(self._default_state))
        for k, v in self._default_state.items():
            if k not in S:
                S[k] = v if not isinstance(v, dict) else dict(v)

        S["tick"] = S.get("tick", 0) + 1
        tick = S["tick"]
        ts = getattr(state, "timestamp", tick * 100)

        mids: Dict[str, float] = {}
        for prod, od in state.order_depths.items():
            m = _get_mid(od)
            if m > 0:
                mids[prod] = m

        for p in list(OURS_FADE) + PEBBLE_ALL:
            if p in mids:
                stats = S["fade"].setdefault(p, [0, 0.0, 0.0])
                _welford_update(stats, mids[p])
                _decay_welford(stats, ROLL_WIN)

        result: Dict[str, List[Order]] = {}

        gh = S.setdefault("gate_mids", {})
        for p in P1_PRODUCTS | OURS_MM:
            if p not in mids:
                continue
            lst = gh.setdefault(p, [])
            lst.append(mids[p])
            if len(lst) > 10:
                del lst[:-10]

        th = S.setdefault("trail_mids", {})
        TRAIL_WIN = 200
        for p in set(OURS_INV_SKEW) | set(P1_INV_SKEW):
            if p not in mids:
                continue
            lst = th.setdefault(p, [])
            lst.append(mids[p])
            if len(lst) > TRAIL_WIN:
                del lst[:-TRAIL_WIN]

        ac = S.setdefault("avg_cost", {})
        last_pos_map = S.setdefault("last_pos", {})
        for prod, ot in (state.own_trades or {}).items():
            if not ot:
                continue
            prev = last_pos_map.get(prod, 0)
            cost = ac.get(prod, 0.0)
            for tr in ot:
                if (
                    getattr(tr, "timestamp", ts) != ts - 100
                    and getattr(tr, "timestamp", ts) != ts
                ):
                    continue
                qty = tr.quantity
                px = tr.price
                buy = getattr(tr, "buyer", "") == "SUBMISSION"
                signed = qty if buy else -qty
                new_prev = prev + signed
                if prev == 0 or (prev > 0 and signed > 0) or (prev < 0 and signed < 0):
                    if new_prev != 0:
                        cost = (cost * abs(prev) + px * abs(signed)) / abs(new_prev)
                elif (prev > 0 and new_prev < 0) or (prev < 0 and new_prev > 0):
                    cost = px
                elif new_prev == 0:
                    cost = 0.0

                prev = new_prev
            ac[prod] = cost

        for prod in mids:
            last_pos_map[prod] = state.position.get(prod, 0)

        self._run_stop_loss(state, mids, S, result)

        self._run_sleep_pods(state, S, result)

        self._run_finam_micro(state, S, result)

        self._run_galaxy(state, S, result)

        self._run_ikkk_triangle(state, S, result)

        self._run_ikkk_snack(state, S, result)

        self._run_yes_pebbles_dir(state, S, result)

        self._run_p2final_anchor(state, S, result)

        self._run_p2(state, mids, S, result)

        self._run_p1(state, mids, S, result)

        self._run_uv(state, S, result)

        self._run_pebbles(state, mids, S, result)

        self._run_panel(state, mids, result)

        self._run_robot_regime(state, mids, S, result)

        self._run_fade(state, mids, ts, S, result)

        self._run_mm(state, mids, S, result)

        if ts >= 980000:
            self._run_eod_flatten(state, mids, result)

        self._enforce_position_limit(state, result)

        for _p in (
            "OXYGEN_SHAKE_MINT",
            "OXYGEN_SHAKE_MORNING_BREATH",
            "ROBOT_DISHES",
            "PANEL_2X2",
        ):
            if _p in result:
                del result[_p]
            _pos = state.position.get(_p, 0)
            if _pos != 0:
                _od = state.order_depths.get(_p)
                if _od is not None:
                    _bb = max(_od.buy_orders) if _od.buy_orders else None
                    _ba = min(_od.sell_orders) if _od.sell_orders else None
                    if _pos > 0 and _bb is not None:
                        result[_p] = [Order(_p, _bb, -_pos)]
                    elif _pos < 0 and _ba is not None:
                        result[_p] = [Order(_p, _ba, -_pos)]

        try:
            traderData = json.dumps(S, separators=(",", ":"))
            if len(traderData) > 49000:
                for p in list(S.get("mid_hist", {}).keys()):
                    S["mid_hist"][p] = S["mid_hist"][p][-30:]
                traderData = json.dumps(S, separators=(",", ":"))
        except Exception:
            traderData = ""

        return result, 0, traderData

    def _run_p2final_anchor(self, state, S, result):
        starts = S.setdefault("tr_starts", {})
        fast = S.setdefault("tr_fast", {})
        slow = S.setdefault("tr_slow", {})
        for product in P2FINAL_ANCHOR_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None:
                continue
            if not od.buy_orders or not od.sell_orders:
                continue
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = od.buy_orders[bid]
            av = -od.sell_orders[ask]
            total = bv + av
            mid = (bid + ask) / 2.0 if total <= 0 else (bid * av + ask * bv) / total
            starts.setdefault(product, mid)
            start_mid = float(starts[product])

            if abs(start_mid - 10000.0) <= 100.0:
                cfg = {"edge": 3, "size": 10, "inv": 0.0}
            elif product == "TRANSLATOR_ECLIPSE_CHARCOAL":
                cfg = {"edge": 4, "size": 6, "inv": 1.40}
            else:
                cfg = {"edge": 4, "size": 5, "inv": 1.50}
            pos = state.position.get(product, 0)
            fair = mid
            ords = []
            passive = True
            fm = float(fast.get(product, mid))
            sm = float(slow.get(product, mid))
            fm = 0.96 * fm + 0.04 * mid
            sm = 0.998 * sm + 0.002 * mid
            fast[product] = fm
            slow[product] = sm

            if abs(start_mid - 10000.0) > 100.0:
                target = 0
                if mid > 10250.0:
                    target = -POSITION_LIMIT
                elif mid < 9750.0:
                    target = POSITION_LIMIT

                delta = target - pos
                if delta > 0:
                    q = min(delta, -od.sell_orders[ask])
                    if q > 0:
                        ords.append(Order(product, ask, q))
                elif delta < 0:
                    q = min(-delta, od.buy_orders[bid])
                    if q > 0:
                        ords.append(Order(product, bid, -q))

            fair -= cfg["inv"] * pos
            expected = pos + sum(o.quantity for o in ords)
            if passive:
                edge = cfg["edge"]
                size = cfg["size"]
                buy_room = POSITION_LIMIT - expected
                sell_room = POSITION_LIMIT + expected
                if buy_room > 0:
                    bid_px = min(bid + 1, math.floor(fair - edge))
                    if bid_px < ask:
                        q = min(size, buy_room)
                        if q > 0:
                            ords.append(Order(product, int(bid_px), q))
                if sell_room > 0:
                    ask_px = max(ask - 1, math.ceil(fair + edge))
                    if ask_px > bid:
                        q = min(size, sell_room)
                        if q > 0:
                            ords.append(Order(product, int(ask_px), -q))
            if ords:
                result.setdefault(product, []).extend(ords)

    def _run_p2(self, state, mids, S, result):
        starts = S.setdefault("p2_starts", {})
        fast = S.setdefault("p2_fast", {})
        slow = S.setdefault("p2_slow", {})

        ANCHOR_PRODUCTS = {
            "TRANSLATOR_ECLIPSE_CHARCOAL",
            "TRANSLATOR_GRAPHITE_MIST",
            "TRANSLATOR_SPACE_GRAY",
        }
        NEAR_ANCHOR_REVERT = {"TRANSLATOR_ASTRO_BLACK", "TRANSLATOR_GRAPHITE_MIST"}

        for product in P2_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None:
                continue
            bb, ba, bv, av = _get_book(od)
            if bb is None or ba is None:
                continue

            total_v = bv + av
            mid = (bb * av + ba * bv) / total_v if total_v > 0 else (bb + ba) / 2.0

            starts.setdefault(product, mid)
            start_mid = float(starts[product])
            pos = state.position.get(product, 0)

            inv = 0.0
            edge = 3
            size = 10
            if abs(start_mid - 10000.0) <= 100.0:
                if product == "TRANSLATOR_ASTRO_BLACK":
                    inv = 0.35
                elif product == "TRANSLATOR_GRAPHITE_MIST":
                    inv = 1.20
            else:
                if product == "TRANSLATOR_ASTRO_BLACK":
                    edge, inv = 3, 0.35
                elif product == "TRANSLATOR_VOID_BLUE":
                    edge, inv = 3, 0.45
                elif product == "TRANSLATOR_ECLIPSE_CHARCOAL":
                    edge, size, inv = 4, 6, 1.40
                elif product == "TRANSLATOR_GRAPHITE_MIST":
                    edge, size, inv = 4, 6, 1.00
                else:
                    edge, size, inv = 4, 5, 1.50

            fair = mid
            orders = []
            use_passive = True

            fast_mid = float(fast.get(product, mid))
            slow_mid = float(slow.get(product, mid))
            fast_mid = 0.96 * fast_mid + 0.04 * mid
            slow_mid = 0.998 * slow_mid + 0.002 * mid
            fast[product] = fast_mid
            slow[product] = slow_mid

            if product in ANCHOR_PRODUCTS and abs(start_mid - 10000.0) > 100.0:
                target = 0
                if product == "TRANSLATOR_GRAPHITE_MIST" and start_mid > 10250.0:
                    use_passive = False
                    if mid > start_mid + 90.0:
                        target = 0
                    elif mid < start_mid - 70.0:
                        target = -POSITION_LIMIT
                    else:
                        target = -5
                elif mid > 10250.0:
                    target = -POSITION_LIMIT
                elif mid < 9750.0:
                    target = POSITION_LIMIT
                orders.extend(self._p2_cross_to_target(product, od, pos, target))
            elif product in NEAR_ANCHOR_REVERT and abs(start_mid - 10000.0) <= 100.0:
                signal = fast_mid - slow_mid
                target = None
                if signal > 30.0:
                    target = -POSITION_LIMIT
                elif signal < -30.0:
                    target = POSITION_LIMIT
                if target is not None:
                    orders.extend(self._p2_cross_to_target(product, od, pos, target))

            fair -= inv * pos

            expected_pos = pos + sum(o.quantity for o in orders)
            if use_passive:
                buy_room = POSITION_LIMIT - expected_pos
                sell_room = POSITION_LIMIT + expected_pos
                if buy_room > 0:
                    bid_price = min(bb + 1, math.floor(fair - edge))
                    if bid_price < ba:
                        qty = min(size, buy_room)
                        if qty > 0:
                            orders.append(Order(product, int(bid_price), qty))
                if sell_room > 0:
                    ask_price = max(ba - 1, math.ceil(fair + edge))
                    if ask_price > bb:
                        qty = min(size, sell_room)
                        if qty > 0:
                            orders.append(Order(product, int(ask_price), -qty))

            if orders:
                result[product] = orders

    def _p2_cross_to_target(self, product, od, pos, target):
        orders = []
        delta = target - pos
        bb, ba, _, _ = _get_book(od)
        if bb is None or ba is None:
            return orders
        if delta > 0:
            qty = min(delta, -od.sell_orders.get(ba, 0))
            if qty > 0:
                orders.append(Order(product, ba, qty))
        elif delta < 0:
            qty = min(-delta, od.buy_orders.get(bb, 0))
            if qty > 0:
                orders.append(Order(product, bb, -qty))
        return orders

    UV_PRODUCTS = (
        "UV_VISOR_YELLOW",
        "UV_VISOR_AMBER",
        "UV_VISOR_MAGENTA",
        "UV_VISOR_ORANGE",
        "UV_VISOR_RED",
    )
    UV_PASSIVE = {
        "UV_VISOR_YELLOW": (3, 6, 6, 0.45),
        "UV_VISOR_AMBER": (3, 10, 10, 0.30),
        "UV_VISOR_ORANGE": (3, 10, 10, 0.30),
        "UV_VISOR_RED": (3, 10, 10, 0.30),
    }
    UV_MAGENTA = {"edge": 4, "size": 6, "skew": 0.35, "thresh": 24.0, "scale": 11.0}
    UV_TREND = {
        "UV_VISOR_AMBER": {"thresh": 34.0, "target": 5, "lot": 2, "beta": 0.35},
        "UV_VISOR_RED": {"thresh": 44.0, "target": 10, "lot": 4, "beta": 1.60},
    }
    UV_FAST_A = 0.18
    UV_SLOW_A = 0.025
    UV_WARMUP = 40
    UV_BAND = 2

    def _uv_micro_mid(self, od):
        if not od.buy_orders or not od.sell_orders:
            return None
        bid = max(od.buy_orders)
        ask = min(od.sell_orders)
        bv = od.buy_orders[bid]
        av = -od.sell_orders[ask]
        tot = bv + av
        if tot <= 0:
            return (bid + ask) / 2.0
        return (bid * av + ask * bv) / tot

    def _uv_make(self, p, od, position, fair, edge, soft, size, target=None):
        orders = []
        bb, ba, _, _ = _get_book(od)
        if bb is None or ba is None:
            return orders
        buy_room = min(POSITION_LIMIT - position, soft - position)
        sell_room = min(POSITION_LIMIT + position, soft + position)
        exp = position
        tgt = 0 if target is None else target
        can_buy = target is None or exp < tgt + self.UV_BAND
        if buy_room > 0 and can_buy:
            bid_px = min(bb + 1, math.floor(fair - edge))
            if bid_px < ba:
                qty = min(size, buy_room)
                if qty > 0:
                    orders.append(Order(p, int(bid_px), qty))
                    exp += qty
        can_sell = target is None or exp > tgt - self.UV_BAND
        if sell_room > 0 and can_sell:
            ask_px = max(ba - 1, math.ceil(fair + edge))
            if ask_px > bb:
                qty = min(size, sell_room)
                if qty > 0:
                    orders.append(Order(p, int(ask_px), -qty))
        return orders

    def _run_uv(self, state, S, result):
        uv = S.setdefault("uv", {"fast": {}, "slow": {}, "count": {}})
        fast = uv["fast"]
        slow = uv["slow"]
        count = uv["count"]
        for p in self.UV_PRODUCTS:
            od = state.order_depths.get(p)
            if od is None:
                continue
            mid = self._uv_micro_mid(od)
            if mid is None:
                continue
            pos = state.position.get(p, 0)
            of = float(fast.get(p, mid))
            os_ = float(slow.get(p, mid))
            nf = of * (1 - self.UV_FAST_A) + mid * self.UV_FAST_A
            ns = os_ * (1 - self.UV_SLOW_A) + mid * self.UV_SLOW_A
            fast[p] = round(nf, 3)
            slow[p] = round(ns, 3)
            count[p] = int(count.get(p, 0)) + 1
            trend = nf - ns
            cnt = count[p]
            if p == "UV_VISOR_MAGENTA":
                cfg = self.UV_MAGENTA
                if cnt < self.UV_WARMUP or abs(trend) <= cfg["thresh"]:
                    tgt = 0
                else:
                    raw = (abs(trend) - cfg["thresh"]) / cfg["scale"]
                    t = min(POSITION_LIMIT, 3 + int(raw))
                    tgt = t if trend > 0 else -t
                fair = mid + 1.4 * trend - cfg["skew"] * (pos - tgt)
                orders = self._uv_make(
                    p, od, pos, fair, cfg["edge"], POSITION_LIMIT, cfg["size"], tgt
                )
            else:
                edge, soft, size, skew = self.UV_PASSIVE[p]
                tcfg = self.UV_TREND.get(p)
                active = []
                tgt = 0
                fair = mid - skew * pos
                if tcfg is not None:
                    if cnt >= self.UV_WARMUP and abs(trend) >= tcfg["thresh"]:
                        tgt = tcfg["target"] if trend > 0 else -tcfg["target"]
                        bb, ba, bv, av = _get_book(od)
                        if bb is not None and ba is not None:
                            if tgt > pos:
                                qty = min(
                                    tcfg["lot"], tgt - pos, POSITION_LIMIT - pos, av
                                )
                                if qty > 0:
                                    active.append(Order(p, ba, qty))
                                    pos += qty
                            elif tgt < pos:
                                qty = min(
                                    tcfg["lot"], pos - tgt, POSITION_LIMIT + pos, bv
                                )
                                if qty > 0:
                                    active.append(Order(p, bb, -qty))
                                    pos -= qty
                    fair = mid + tcfg["beta"] * trend - skew * (pos - tgt)
                orders = self._uv_make(p, od, pos, fair, edge, soft, size)
                if active:
                    orders = active + orders
            if orders:
                result[p] = orders

    def _run_p1(self, state, mids, S, result):
        ema = S.setdefault("p1_ema", {})
        last_mids = S.get("p1_last", {})

        pair_adj: Dict[str, float] = {}
        for a, b, key, beta in P1_PAIRS:
            if a not in mids or b not in mids:
                continue
            current_sum = mids[a] + mids[b]
            old_sum = float(ema.get(key, current_sum))
            deviation = current_sum - old_sum
            adj = -0.5 * beta * deviation
            pair_adj[a] = pair_adj.get(a, 0.0) + adj
            pair_adj[b] = pair_adj.get(b, 0.0) + adj
            ema[key] = old_sum * 0.985 + current_sum * 0.015

        for product in P1_PRODUCTS:
            if self._in_stop_cooldown(product, S):
                continue
            od = state.order_depths.get(product)
            if od is None:
                continue
            bb, ba, bv, av = _get_book(od)
            if bb is None or ba is None:
                continue

            total_v = bv + av
            mid = (bb * av + ba * bv) / total_v if total_v > 0 else (bb + ba) / 2.0
            pos = state.position.get(product, 0)

            fair = mid + pair_adj.get(product, 0.0)

            prev = last_mids.get(product)
            if prev is not None and product in P1_MEAN_REVERT:
                gamma, threshold = P1_MEAN_REVERT[product]
                move = mid - float(prev)
                if abs(move) >= threshold:
                    fair -= gamma * move
                else:
                    fair -= 0.10 * gamma * move

            if product.startswith("PEBBLES_") and all(p in mids for p in PEBBLE_ALL):
                basket_err = sum(mids[p] for p in PEBBLE_ALL) - 50000.0
                if abs(basket_err) > 3.0:
                    fair += -PEBBLE_BASKET_BETA * basket_err / 5.0

            orders = []
            buy_room = POSITION_LIMIT - pos
            sell_room = POSITION_LIMIT + pos

            for price in sorted(od.sell_orders):
                if buy_room <= 0:
                    break
                if price <= fair - 2:
                    qty = min(-od.sell_orders[price], buy_room)
                    if qty > 0:
                        orders.append(Order(product, price, qty))
                        buy_room -= qty

            for price in sorted(od.buy_orders, reverse=True):
                if sell_room <= 0:
                    break
                if price >= fair + 2:
                    qty = min(od.buy_orders[price], sell_room)
                    if qty > 0:
                        orders.append(Order(product, price, -qty))
                        sell_room -= qty

            expected_pos = pos + sum(o.quantity for o in orders)
            passive_edge = 3
            drift_bps = self._trend_drift_bps(product, S)
            block_bid = (
                expected_pos >= self.GATE_INV_CAP and drift_bps < -self.GATE_THR_BPS
            )
            block_ask = (
                expected_pos <= -self.GATE_INV_CAP and drift_bps > self.GATE_THR_BPS
            )
            if POSITION_LIMIT - expected_pos > 0 and not block_bid:
                bid_price = min(bb + 1, math.floor(fair - passive_edge))
                if bid_price < ba:
                    qty = min(10, POSITION_LIMIT - expected_pos)
                    if qty > 0:
                        orders.append(Order(product, int(bid_price), qty))

            if POSITION_LIMIT + expected_pos > 0 and not block_ask:
                ask_price = max(ba - 1, math.ceil(fair + passive_edge))
                if ask_price > bb:
                    qty = min(10, POSITION_LIMIT + expected_pos)
                    if qty > 0:
                        orders.append(Order(product, int(ask_price), -qty))

            if orders:
                result[product] = orders

        S["p1_last"] = {p: round(v, 3) for p, v in mids.items()}

    def _run_pebbles(self, state, mids, S, result):
        if not all(p in mids for p in PEBBLE_ALL):
            return
        basket_sum = sum(mids[p] for p in PEBBLE_ALL)
        basket_error = basket_sum - 50000.0

        for p in PEBBLES_HOLD_SHORT:
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            pos = state.position.get(p, 0)
            target = -POSITION_LIMIT
            diff = target - pos
            if diff < 0:
                orders = []
                remaining = -diff
                for bid_px in sorted(od.buy_orders.keys(), reverse=True):
                    if remaining <= 0:
                        break
                    fill = min(remaining, od.buy_orders[bid_px])
                    if fill > 0:
                        orders.append(Order(p, bid_px, -fill))
                        remaining -= fill
                if remaining > 0:
                    orders.append(Order(p, ba - 1, -remaining))
                if orders:
                    result[p] = orders

        for p in PEBBLES_HOLD_LONG:
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            pos = state.position.get(p, 0)
            target = POSITION_LIMIT
            diff = target - pos
            if diff > 0:
                orders = []
                remaining = diff
                for ask_px in sorted(od.sell_orders.keys()):
                    if remaining <= 0:
                        break
                    fill = min(remaining, -od.sell_orders[ask_px])
                    if fill > 0:
                        orders.append(Order(p, ask_px, fill))
                        remaining -= fill
                if remaining > 0:
                    orders.append(Order(p, bb + 1, remaining))
                if orders:
                    result[p] = orders

        for p in PEBBLES_MM:
            if p in result:
                continue
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            pos = state.position.get(p, 0)
            mid = mids[p]
            fair = mid
            if abs(basket_error) > 3.0:
                fair += -PEBBLE_BASKET_BETA * basket_error / 5.0

            passive_edge = 3
            bid_price = min(bb + 1, int(fair - passive_edge))
            ask_price = max(ba - 1, int(fair + passive_edge + 0.999))
            orders = []

            buy_room = POSITION_LIMIT - pos
            for price in sorted(od.sell_orders.keys()):
                if buy_room <= 0:
                    break
                if price <= fair - 1:
                    qty = min(-od.sell_orders[price], buy_room)
                    if qty > 0:
                        orders.append(Order(p, price, qty))
                        buy_room -= qty

            sell_room = POSITION_LIMIT + pos
            for price in sorted(od.buy_orders.keys(), reverse=True):
                if sell_room <= 0:
                    break
                if price >= fair + 1:
                    qty = min(od.buy_orders[price], sell_room)
                    if qty > 0:
                        orders.append(Order(p, price, -qty))
                        sell_room -= qty

            expected_pos = pos + sum(o.quantity for o in orders)
            rb = POSITION_LIMIT - expected_pos
            rs = POSITION_LIMIT + expected_pos
            if rb > 0 and bid_price < ba:
                orders.append(Order(p, int(bid_price), rb))
            if rs > 0 and ask_price > bb:
                orders.append(Order(p, int(ask_price), -rs))

            if orders:
                result[p] = orders

        pm = "PEBBLES_M"
        if pm in mids:
            hist = S["peb_m_hist"]
            hist.append(mids[pm])
            if len(hist) > PEBBLES_M_FADE_WIN:
                del hist[: len(hist) - PEBBLES_M_FADE_WIN]
            if len(hist) >= 200:
                n = len(hist)
                mu = sum(hist) / n
                var = sum((x - mu) ** 2 for x in hist) / n
                sd = var**0.5
                if sd >= 1e-6:
                    z = (mids[pm] - mu) / sd
                    od = state.order_depths.get(pm)
                    if od is not None:
                        bb, ba, _, _ = _get_book(od)
                        if bb is not None and ba is not None:
                            pos = state.position.get(pm, 0)
                            if z > PEBBLES_M_Z_IN and pos > -POSITION_LIMIT:
                                result[pm] = [Order(pm, bb, -POSITION_LIMIT - pos)]
                            elif z < -PEBBLES_M_Z_IN and pos < POSITION_LIMIT:
                                result[pm] = [Order(pm, ba, POSITION_LIMIT - pos)]

    def _run_robot_regime(self, state, mids, S, result):
        tick = S["tick"]

        opens = S["robot_open_prices"]
        all_leaders = set()
        for leaders in REGIME_TARGETS.values():
            all_leaders.update(leaders)
        for prod in all_leaders:
            if prod in mids and prod not in opens:
                opens[prod] = mids[prod]

        if "regime_signals" not in S:
            S["regime_signals"] = {}
        if tick == ROBOT_DECIDE_TICK and not S["regime_signals"]:
            for tgt, leaders in REGIME_TARGETS.items():
                sig = self._leader_vote(leaders, opens, mids)
                if tgt in REGIME_INVERTED:
                    sig = -sig
                S["regime_signals"][tgt] = sig

        for p, leaders in REGIME_TARGETS.items():
            if p not in mids:
                continue
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            pos = state.position.get(p, 0)
            sig = S["regime_signals"].get(p) if tick >= ROBOT_DECIDE_TICK else None

            if sig is not None and sig != 0:
                target = sig * POSITION_LIMIT
                AGGR_PER_TICK = 0
                orders = []
                if target > pos:
                    rem = target - pos
                    aggr = AGGR_PER_TICK
                    for px in sorted(od.sell_orders.keys()):
                        if rem <= 0 or aggr <= 0:
                            break
                        qty = min(-od.sell_orders[px], rem, aggr)
                        if qty > 0:
                            orders.append(Order(p, px, qty))
                            rem -= qty
                            aggr -= qty
                    if rem > 0 and bb + 1 < ba:
                        orders.append(Order(p, bb + 1, rem))
                elif target < pos:
                    rem = pos - target
                    aggr = AGGR_PER_TICK
                    for px in sorted(od.buy_orders.keys(), reverse=True):
                        if rem <= 0 or aggr <= 0:
                            break
                        qty = min(od.buy_orders[px], rem, aggr)
                        if qty > 0:
                            orders.append(Order(p, px, -qty))
                            rem -= qty
                            aggr -= qty
                    if rem > 0 and ba - 1 > bb:
                        orders.append(Order(p, ba - 1, -rem))
                if orders:
                    result[p] = orders
            else:
                if p in REGIME_NO_PRE_TRADE and tick < ROBOT_DECIDE_TICK:
                    continue
                if ba - bb < 4:
                    continue
                CAP = 3
                orders = []
                if pos > CAP:
                    orders.append(Order(p, bb, -(pos - CAP)))
                elif pos < -CAP:
                    orders.append(Order(p, ba, -(pos + CAP)))
                else:
                    buy_room = max(0, CAP - pos)
                    sell_room = max(0, CAP + pos)
                    if buy_room > 0:
                        orders.append(Order(p, bb + 1, buy_room))
                    if sell_room > 0:
                        orders.append(Order(p, ba - 1, -sell_room))
                if orders:
                    result[p] = orders

    def _leader_vote(self, leaders, opens, mids):
        signs = []
        for L in leaders:
            if L in opens and L in mids:
                chg = mids[L] - opens[L]
                if chg > 0:
                    signs.append(1)
                elif chg < 0:
                    signs.append(-1)
                else:
                    signs.append(0)
        if not signs:
            return 0

        if all(s > 0 for s in signs):
            return 1
        if all(s < 0 for s in signs):
            return -1
        return 0

    def _run_robot_tight_mm(self, state, mids, result):
        for p in ["ROBOT_VACUUMING", "ROBOT_MOPPING"]:
            if p not in mids:
                continue
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            if ba - bb < 4:
                continue
            pos = state.position.get(p, 0)
            CAP = 3
            orders = []
            if pos > CAP and bb is not None:
                orders.append(Order(p, bb, -(pos - CAP)))
            elif pos < -CAP and ba is not None:
                orders.append(Order(p, ba, -(pos + CAP)))
            else:
                buy_room = max(0, CAP - pos)
                sell_room = max(0, CAP + pos)
                if buy_room > 0:
                    orders.append(Order(p, bb + 1, buy_room))
                if sell_room > 0:
                    orders.append(Order(p, ba - 1, -sell_room))
            if orders:
                result[p] = orders

    def _run_robot_pairs(self, state, mids, S, result):
        m_p, v_p = "ROBOT_MOPPING", "ROBOT_VACUUMING"
        if m_p not in mids or v_p not in mids:
            return
        spread = mids[m_p] - mids[v_p]
        hist = S["robot_spread_hist"]
        hist.append(spread)
        if len(hist) > ROBOT_PAIR_WIN:
            del hist[: len(hist) - ROBOT_PAIR_WIN]
        if len(hist) < 200:
            return
        n = len(hist)
        mu = sum(hist) / n
        var = sum((x - mu) ** 2 for x in hist) / n
        sd = var**0.5
        if sd < 1e-6:
            return
        z = (spread - mu) / sd

        m_od = state.order_depths.get(m_p)
        v_od = state.order_depths.get(v_p)
        if m_od is None or v_od is None:
            return
        m_bb, m_ba, _, _ = _get_book(m_od)
        v_bb, v_ba, _, _ = _get_book(v_od)
        if None in (m_bb, m_ba, v_bb, v_ba):
            return
        m_pos = state.position.get(m_p, 0)
        v_pos = state.position.get(v_p, 0)

        if z > ROBOT_PAIR_Z_IN:
            if m_pos > -POSITION_LIMIT:
                result[m_p] = [Order(m_p, m_bb, -POSITION_LIMIT - m_pos)]
            if v_pos < POSITION_LIMIT:
                result[v_p] = [Order(v_p, v_ba, POSITION_LIMIT - v_pos)]
        elif z < -ROBOT_PAIR_Z_IN:
            if m_pos < POSITION_LIMIT:
                result[m_p] = [Order(m_p, m_ba, POSITION_LIMIT - m_pos)]
            if v_pos > -POSITION_LIMIT:
                result[v_p] = [Order(v_p, v_bb, -POSITION_LIMIT - v_pos)]

    def _run_panel(self, state, mids, result):
        if not all(p in mids for p in PANEL_ALL):
            return
        basket_error = sum(mids[p] for p in PANEL_ALL) - PANEL_BASKET_SUM
        for p in PANEL_ARB:
            od = state.order_depths.get(p)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            pos = state.position.get(p, 0)
            mid = mids[p]
            fair = mid - PANEL_BETA * basket_error / 5.0
            orders = []
            buy_room = POSITION_LIMIT - pos
            for px in sorted(od.sell_orders.keys()):
                if buy_room <= 0:
                    break
                if px <= fair - 1:
                    qty = min(-od.sell_orders[px], buy_room)
                    if qty > 0:
                        orders.append(Order(p, px, qty))
                        buy_room -= qty
            sell_room = POSITION_LIMIT + pos
            for px in sorted(od.buy_orders.keys(), reverse=True):
                if sell_room <= 0:
                    break
                if px >= fair + 1:
                    qty = min(od.buy_orders[px], sell_room)
                    if qty > 0:
                        orders.append(Order(p, px, -qty))
                        sell_room -= qty
            expected_pos = pos + sum(o.quantity for o in orders)
            rem_buy = POSITION_LIMIT - expected_pos
            rem_sell = POSITION_LIMIT + expected_pos
            bid_price = min(bb + 1, int(fair - PANEL_EDGE))
            ask_price = max(ba - 1, int(fair + PANEL_EDGE + 0.999))
            if rem_buy > 0 and bid_price < ba:
                orders.append(Order(p, int(bid_price), rem_buy))
            if rem_sell > 0 and ask_price > bb:
                orders.append(Order(p, int(ask_price), -rem_sell))
            if orders:
                result[p] = orders

    def _run_fade(self, state, mids, ts, S, result):
        tick = S["tick"]
        for p in OURS_FADE:
            if p in result:
                continue
            if p not in mids:
                continue
            od = state.order_depths.get(p)
            if od is None:
                continue
            stats = S["fade"].get(p)
            if not stats or stats[0] < 200:
                continue
            sd = _welford_std(stats)
            if sd < 1e-6:
                continue
            mu = stats[1]
            mid = mids[p]
            z = (mid - mu) / sd
            pos = state.position.get(p, 0)
            active_dir = S["fade_active"].get(p, 0)

            if tick < FIRST_500_BLOCK and active_dir == 0:
                continue

            bb, ba, _, _ = _get_book(od)
            z_in, z_out = FADE_OVERRIDES.get(p, (FADE_Z_IN, FADE_Z_IN))

            if active_dir > 0 and z > z_out:
                if pos > 0 and bb is not None:
                    self._add(result, p, Order(p, bb, -pos))
                S["fade_active"][p] = 0
                continue
            if active_dir < 0 and z < -z_out:
                if pos < 0 and ba is not None:
                    self._add(result, p, Order(p, ba, -pos))
                S["fade_active"][p] = 0
                continue

            if active_dir == 0:
                signal = 0
                if z > z_in:
                    signal = -1
                elif z < -z_in:
                    signal = 1
                if signal == 0:
                    continue
                if signal > 0 and ba is not None:
                    self._add(result, p, Order(p, ba, FADE_SIZE - pos))
                elif signal < 0 and bb is not None:
                    self._add(result, p, Order(p, bb, -FADE_SIZE - pos))
                S["fade_active"][p] = signal

    def _run_mm(self, state, mids, S, result):
        for p in OURS_MM:
            if p in result:
                continue
            if self._in_stop_cooldown(p, S):
                continue
            od = state.order_depths.get(p)
            if od is None:
                continue
            if p not in mids:
                continue
            bb, ba, _, _ = _get_book(od)
            if bb is None or ba is None:
                continue
            if ba - bb < 3:
                continue
            our_bid = bb + 1
            our_ask = ba - 1
            if our_bid >= our_ask:
                continue
            pos = state.position.get(p, 0)
            drift_bps = self._trend_drift_bps(p, S)
            block_bid = pos >= self.GATE_INV_CAP and drift_bps < -self.GATE_THR_BPS
            block_ask = pos <= -self.GATE_INV_CAP and drift_bps > self.GATE_THR_BPS
            if pos < POSITION_LIMIT and not block_bid:
                self._add(result, p, Order(p, int(our_bid), POSITION_LIMIT - pos))
            if pos > -POSITION_LIMIT and not block_ask:
                self._add(result, p, Order(p, int(our_ask), -POSITION_LIMIT - pos))

    def _run_eod_flatten(self, state, mids, result):
        for prod, pos in state.position.items():
            if pos == 0:
                continue

            if prod in PEBBLES_HOLD_SHORT or prod in PEBBLES_HOLD_LONG:
                continue
            if prod in self.UV_PRODUCTS:
                continue
            if prod in P2FINAL_ANCHOR_PRODUCTS:
                continue
            if prod in SLEEP_POD_PRODUCTS:
                continue
            if prod in MICRO_FINAM_PRODUCTS:
                continue
            if prod in GALAXY_PRODUCTS:
                continue
            if prod in IKKK_TRIANGLE_PRODUCTS:
                continue
            if prod in IKKK_SNACK_PRODUCTS:
                continue
            if prod in YES_PEB_DIR_PRODUCTS:
                continue
            od = state.order_depths.get(prod)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if pos > 0 and bb is not None:
                result[prod] = [Order(prod, bb, -pos)]
            elif pos < 0 and ba is not None:
                result[prod] = [Order(prod, ba, -pos)]

    def _in_stop_cooldown(self, prod, S):
        st = S.get("stopped", {}).get(prod)
        if st is None:
            return False
        return (S.get("tick", 0) - st) < self.STOP_COOLDOWN_TICKS

    def _trend_drift_bps(self, prod, S):
        lst = S.get("gate_mids", {}).get(prod)
        if not lst or len(lst) < 10:
            return 0.0
        old = lst[0]
        cur = lst[-1]
        if old <= 0:
            return 0.0
        return (cur - old) / old * 10000.0

    GATE_THR_BPS = 10.0
    GATE_INV_CAP = 5
    STOP_BPS = 150.0
    STOP_MIN_POS = 3
    STOP_COOLDOWN_TICKS = 50

    STOP_BPS_OVERRIDE = {
        "ROBOT_DISHES": 100.0,
    }

    def _run_sleep_pods(self, state, S, result):
        starts = S.setdefault("sleep_starts", {})
        for product in SLEEP_POD_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = int(od.buy_orders[bid])
            av = int(-od.sell_orders[ask])
            tot = bv + av
            mid = (bid * av + ask * bv) / tot if tot > 0 else (bid + ask) / 2.0
            starts.setdefault(product, mid)
            sm = float(starts[product])
            thr, lo_t, hi_t, edge, size, lot, skew = SLEEP_PARAMS[product]
            if product == "SLEEP_POD_NYLON":
                target = lo_t if sm >= thr else hi_t
            else:
                target = lo_t if sm < thr else hi_t
            pos = int(state.position.get(product, 0))
            orders = []
            d = target - pos
            if d > 0:
                q = min(d, av, POSITION_LIMIT - pos, lot)
                if q > 0:
                    orders.append(Order(product, int(ask), q))
                    pos += q
            elif d < 0:
                q = min(-d, bv, POSITION_LIMIT + pos, lot)
                if q > 0:
                    orders.append(Order(product, int(bid), -q))
                    pos -= q
            fair = mid - skew * (pos - target)
            band = 2
            br = POSITION_LIMIT - pos
            sr = POSITION_LIMIT + pos
            if br > 0 and pos < target + band:
                bp = min(bid + 1, math.floor(fair - edge))
                if bp < ask:
                    q = min(size, br)
                    if q > 0:
                        orders.append(Order(product, int(bp), q))
                        pos += q
            if sr > 0 and pos > target - band:
                ap = max(ask - 1, math.ceil(fair + edge))
                if ap > bid:
                    q = min(size, sr)
                    if q > 0:
                        orders.append(Order(product, int(ap), -q))
            if orders:
                result[product] = orders

    def _run_finam_micro(self, state, S, result):
        starts = S.setdefault("fmicro_starts", {})
        flags = S.setdefault("fmicro_conf", {})
        for product in MICRO_FINAM_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = int(od.buy_orders[bid])
            av = int(-od.sell_orders[ask])
            cm = (bid + ask) / 2.0
            starts.setdefault(product, cm)
            sm = float(starts[product])
            if product == "MICROCHIP_OVAL":
                d = -1
            elif product == "MICROCHIP_CIRCLE":
                d = 1 if sm < 8700.0 else -1
            elif product == "MICROCHIP_SQUARE":
                d = -1 if sm > 15000.0 else 1
            else:
                d = 0
            lim = 10 if product in MICRO_FINAM_CORE else 5
            if product in MICRO_FINAM_CORE:
                ok = True
            else:
                ok = False
                if flags.get(product):
                    if d > 0 and cm <= sm:
                        flags[product] = False
                    elif d < 0 and cm >= sm:
                        flags[product] = False
                    else:
                        ok = True
                if not ok:
                    if d > 0 and cm >= sm + 60.0:
                        flags[product] = True
                        ok = True
                    elif d < 0 and cm <= sm - 60.0:
                        flags[product] = True
                        ok = True
            tgt = d * lim if ok else 0
            pos = state.position.get(product, 0)
            orders = []
            if tgt > pos:
                q = min(tgt - pos, lim - pos, av)
                if q > 0:
                    orders.append(Order(product, ask, q))
            elif tgt < pos:
                q = min(pos - tgt, lim + pos, bv)
                if q > 0:
                    orders.append(Order(product, bid, -q))
            if orders:
                result[product] = orders

    def _run_galaxy(self, state, S, result):
        starts = S.setdefault("gal_starts", {})
        lows = S.setdefault("gal_lows", {})
        locked = S.setdefault("gal_locked", {})
        for product in GALAXY_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = int(od.buy_orders[bid])
            av = int(-od.sell_orders[ask])
            tot = bv + av
            mid = (bid * av + ask * bv) / tot if tot > 0 else (bid + ask) / 2.0
            starts.setdefault(product, mid)
            sm = float(starts[product])
            thr, lo_t, hi_t = GAL_BASE[product]
            base = lo_t if sm < thr else hi_t
            target = base
            if product == "GALAXY_SOUNDS_SOLAR_WINDS" and base < 0:
                low = min(float(lows.get(product, mid)), mid)
                lows[product] = low
                if locked.get(product):
                    target = -3
                elif sm - low >= 180.0 and mid - low >= 100.0:
                    locked[product] = True
                    target = -3
            ge, gs, lot, gk = GAL_PARAMS[product]
            pos = int(state.position.get(product, 0))
            orders = []
            d = target - pos
            if d > 0:
                q = min(d, av, POSITION_LIMIT - pos, lot)
                if q > 0:
                    orders.append(Order(product, int(ask), q))
                    pos += q
            elif d < 0:
                q = min(-d, bv, POSITION_LIMIT + pos, lot)
                if q > 0:
                    orders.append(Order(product, int(bid), -q))
                    pos -= q
            fair = mid - gk * (pos - target)
            br = POSITION_LIMIT - pos
            sr = POSITION_LIMIT + pos
            if br > 0 and pos < target + 2:
                bp = min(bid + 1, math.floor(fair - ge))
                if bp < ask:
                    q = min(gs, br)
                    if q > 0:
                        orders.append(Order(product, int(bp), q))
                        pos += q
            if sr > 0 and pos > target - 2:
                ap = max(ask - 1, math.ceil(fair + ge))
                if ap > bid:
                    q = min(gs, sr)
                    if q > 0:
                        orders.append(Order(product, int(ap), -q))
            if orders:
                result[product] = orders

    def _run_yes_pebbles_dir(self, state, S, result):
        LIMIT = 10
        LOT = 4
        EDGE = 4
        SKEW = 0.20
        BAND = 2
        starts = S.setdefault("yes_peb_starts", {})
        all_mids = {}
        for p in PEBBLE_ALL:
            od = state.order_depths.get(p)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = od.buy_orders[bid]
            av = -od.sell_orders[ask]
            tot = bv + av
            mm = (bid * av + ask * bv) / tot if tot > 0 else (bid + ask) / 2.0
            all_mids[p] = mm
        basket_adj = 0.0
        if all(p in all_mids for p in PEBBLE_ALL):
            err = sum(all_mids[p] for p in PEBBLE_ALL) - 50000.0
            if abs(err) >= 4.0:
                basket_adj = -0.18 * err / 5.0
        for product in YES_PEB_DIR_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or product not in all_mids:
                continue
            mid = all_mids[product]
            starts.setdefault(product, mid)
            start_mid = float(starts[product])
            if product == "PEBBLES_XL":
                target = -10 if start_mid > 13000.0 else 10
            elif product == "PEBBLES_S":
                target = -6
            else:
                target = 0
            SIZE = YES_PEB_DIR_SIZE.get(product, 4)
            pos = state.position.get(product, 0)
            bid = max(od.buy_orders)
            ask = min(od.sell_orders)
            bv = od.buy_orders[bid]
            av = -od.sell_orders[ask]
            orders = []
            if target > pos:
                q = min(target - pos, LIMIT - pos, av, LOT)
                if q > 0:
                    orders.append(Order(product, ask, q))
                    pos += q
            elif target < pos:
                q = min(pos - target, LIMIT + pos, bv, LOT)
                if q > 0:
                    orders.append(Order(product, bid, -q))
                    pos -= q
            fair = mid + basket_adj - SKEW * (pos - target)
            buy_room = LIMIT - pos
            sell_room = LIMIT + pos
            if buy_room > 0 and pos < min(LIMIT, target + BAND):
                bp = min(bid + 1, math.floor(fair - EDGE))
                if bp < ask:
                    q = min(SIZE, buy_room)
                    if q > 0:
                        orders.append(Order(product, int(bp), q))
            if sell_room > 0 and pos > max(-LIMIT, target - BAND):
                ap = max(ask - 1, math.ceil(fair + EDGE))
                if ap > bid:
                    q = min(SIZE, sell_room)
                    if q > 0:
                        orders.append(Order(product, int(ap), -q))
            if orders:
                result[product] = orders

    def _run_ikkk_snack(self, state, S, result):
        LIMIT = 10
        hist_all = S.setdefault("ikkk_snack_hist", {})
        tgt_all = S.setdefault("ikkk_snack_tgt", {})
        for product in IKKK_SNACK_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or (not od.buy_orders and not od.sell_orders):
                continue
            window, entry, start_tgt = IKKK_SNACK_PARAMS[product]
            if od.buy_orders and od.sell_orders:
                mid2 = max(od.buy_orders) + min(od.sell_orders)
            elif od.buy_orders:
                mid2 = 2 * max(od.buy_orders)
            elif od.sell_orders:
                mid2 = 2 * min(od.sell_orders)
            else:
                continue
            hist = hist_all.setdefault(product, [])
            target = int(tgt_all.get(product, start_tgt))
            entry2 = 2 * entry
            if mid2 > 0 and len(hist) >= window:
                fair2 = sum(hist[-window:]) / window
                diff2 = mid2 - fair2
                if diff2 > entry2:
                    target = -LIMIT
                elif diff2 < -entry2:
                    target = LIMIT
            if mid2 > 0:
                hist.append(int(mid2))
                if len(hist) > 500:
                    del hist[: len(hist) - 500]
            tgt_all[product] = target
            pos = int(state.position.get(product, 0))
            need = target - pos
            orders = []
            if need > 0:
                left = min(need, LIMIT - pos)
                for ask in sorted(od.sell_orders):
                    if left <= 0:
                        break
                    avail = -od.sell_orders[ask]
                    take = min(left, avail)
                    if take > 0:
                        orders.append(Order(product, int(ask), int(take)))
                        left -= take
            elif need < 0:
                left = min(-need, LIMIT + pos)
                for bid in sorted(od.buy_orders, reverse=True):
                    if left <= 0:
                        break
                    avail = od.buy_orders[bid]
                    take = min(left, avail)
                    if take > 0:
                        orders.append(Order(product, int(bid), int(-take)))
                        left -= take
            if orders:
                result[product] = orders

    def _run_ikkk_triangle(self, state, S, result):
        LIMIT = 10
        for product in IKKK_TRIANGLE_PRODUCTS:
            od = state.order_depths.get(product)
            if od is None or not od.buy_orders or not od.sell_orders:
                continue
            bb = max(od.buy_orders)
            ba = min(od.sell_orders)
            spread = ba - bb
            if spread < 2:
                continue
            fair = (bb + ba) / 2.0
            pos = state.position.get(product, 0)
            existing = result.get(product, [])
            ub = sum(o.quantity for o in existing if o.quantity > 0)
            us = -sum(o.quantity for o in existing if o.quantity < 0)
            buy_cap = LIMIT - pos - ub
            sell_cap = LIMIT + pos - us
            if buy_cap <= 0 and sell_cap <= 0:
                continue
            orders = []
            threshold = max(2, spread // 2)
            for ask in sorted(od.sell_orders):
                if ask <= fair - threshold and buy_cap > 0:
                    avail = -od.sell_orders[ask]
                    q = min(avail, buy_cap)
                    if q > 0:
                        orders.append(Order(product, ask, q))
                        buy_cap -= q
                else:
                    break
            for bid in sorted(od.buy_orders, reverse=True):
                if bid >= fair + threshold and sell_cap > 0:
                    avail = od.buy_orders[bid]
                    q = min(avail, sell_cap)
                    if q > 0:
                        orders.append(Order(product, bid, -q))
                        sell_cap -= q
                else:
                    break
            bid_px = bb + 1
            ask_px = ba - 1
            if bid_px >= ask_px:
                bid_px = bb
                ask_px = ba
            if bid_px > fair - 1:
                bid_px = int(fair) - 1
            if ask_px < fair + 1:
                ask_px = int(fair) + 1
            if pos >= 7:
                ask_px -= 1
            elif pos <= -7:
                bid_px += 1
            if bid_px < ask_px:
                if buy_cap > 0:
                    orders.append(Order(product, bid_px, buy_cap))
                if sell_cap > 0:
                    orders.append(Order(product, ask_px, -sell_cap))
            if orders:
                result.setdefault(product, []).extend(orders)

    def _run_stop_loss(self, state, mids, S, result):
        ac = S.get("avg_cost", {})
        stopped = S.setdefault("stopped", {})
        tick = S.get("tick", 0)
        if "stop_ovr" not in S:
            ovr = dict(self.STOP_BPS_OVERRIDE)
            S["stop_ovr"] = ovr
        ovr = S["stop_ovr"]
        for prod, pos in state.position.items():
            if abs(pos) < self.STOP_MIN_POS:
                continue
            if prod not in mids:
                continue
            cost = ac.get(prod, 0.0)
            if cost <= 0:
                continue
            mid = mids[prod]
            if pos > 0:
                loss_bps = (cost - mid) / cost * 10000.0
            else:
                loss_bps = (mid - cost) / cost * 10000.0
            if prod not in ovr:
                continue
            thr = ovr[prod]
            if loss_bps < thr:
                continue
            od = state.order_depths.get(prod)
            if od is None:
                continue
            bb, ba, _, _ = _get_book(od)
            if pos > 0 and bb is not None:
                result[prod] = [Order(prod, bb, -pos)]
                stopped[prod] = tick
                ac[prod] = 0.0
            elif pos < 0 and ba is not None:
                result[prod] = [Order(prod, ba, -pos)]
                stopped[prod] = tick
                ac[prod] = 0.0

    def _add(self, result, prod, order):
        if order is None or order.quantity == 0:
            return
        result.setdefault(prod, []).append(order)

    def _enforce_position_limit(self, state, result):
        for prod, orders in list(result.items()):
            if not orders:
                continue
            if prod in self.UV_PRODUCTS:
                continue
            if prod in P2FINAL_ANCHOR_PRODUCTS:
                continue
            if prod in SLEEP_POD_PRODUCTS:
                continue
            if prod in MICRO_FINAM_PRODUCTS:
                continue
            if prod in GALAXY_PRODUCTS:
                continue
            if prod in IKKK_TRIANGLE_PRODUCTS:
                continue
            if prod in IKKK_SNACK_PRODUCTS:
                continue
            if prod in YES_PEB_DIR_PRODUCTS:
                continue
            pos = state.position.get(prod, 0)
            buys = [o for o in orders if o.quantity > 0]
            sells = [o for o in orders if o.quantity < 0]
            buy_sum = sum(o.quantity for o in buys)
            sell_sum = sum(o.quantity for o in sells)
            buy_room = POSITION_LIMIT - pos
            sell_room = POSITION_LIMIT + pos
            if buy_sum > max(0, buy_room) and buy_sum > 0:
                scale = max(0, buy_room) / buy_sum
                for o in buys:
                    o.quantity = max(0, int(o.quantity * scale))
            if abs(sell_sum) > max(0, sell_room) and sell_sum < 0:
                scale = max(0, sell_room) / abs(sell_sum)
                for o in sells:
                    o.quantity = -max(0, int(abs(o.quantity) * scale))
            result[prod] = [o for o in orders if o.quantity != 0]
            if not result[prod]:
                del result[prod]
