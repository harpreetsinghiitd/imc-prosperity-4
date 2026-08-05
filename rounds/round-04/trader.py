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


HG_EMA_ALPHA = 0.00005
HG_EMA_INIT = 9995.0
HG_OU_ENTRY = 31.0
HG_OU_EXIT = 0.0
HG_OU_QTY = 20
HG_MM_SPREAD = 7
HG_MM_SIZE = 15
HG_HISTORY = 250


M38_DECAY = 0.92
M38_SCALE = 0.10
M38_MAX = 3.0


STRIKES = {
    "VEV_4000": 4000,
    "VEV_4500": 4500,
    "VEV_5000": 5000,
    "VEV_5100": 5100,
    "VEV_5200": 5200,
    "VEV_5300": 5300,
    "VEV_5400": 5400,
    "VEV_5500": 5500,
    "VEV_6000": 6000,
    "VEV_6500": 6500,
}
ATM_STRIKES = ["VEV_5000", "VEV_5100", "VEV_5200", "VEV_5300", "VEV_5400", "VEV_5500"]
ZONE_VOUCHERS = [
    "VEV_4500",
    "VEV_5000",
    "VEV_5100",
    "VEV_5200",
    "VEV_5300",
    "VEV_5400",
    "VEV_5500",
]

VE_EMA_ALPHA = 0.00003
ZONE_OFF = 20
ZONE_OFF_TREND = 40
FLAT_OFF = 5

TREND_TICKS = 700
CRASH_COOL = 200

VOL_ALPHA = 0.02
BS_REJECT = 3.0


VE_CP_DECAY = 0.98
VE_CP_SCALE = 0.045
VE_CP_MAX = 5.0
VE_CP_WEIGHTS = {
    "Mark 67": +1.50,
    "Mark 14": -0.30,
}


def norm_cdf(x):
    if x < -10:
        return 0.0
    if x > 10:
        return 1.0
    s = 1
    if x < 0:
        s = -1
        x = -x
    t = 1.0 / (1.0 + 0.2316419 * x)
    y = 0.3989422804014327 * math.exp(-x * x / 2.0)
    p = (
        (((1.330274429 * t - 1.821255978) * t + 1.781477937) * t - 0.356563782) * t
        + 0.319381530
    ) * t
    return 0.5 + s * (0.5 - y * p)


def bs_call(S, K, T, sigma):
    if T <= 1e-10 or sigma <= 1e-10:
        return max(S - K, 0.0)
    sT = math.sqrt(T)
    d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sT)
    return S * norm_cdf(d1) - K * norm_cdf(d1 - sigma * sT)


def bs_iv(mp, S, K, T):
    intrinsic = max(S - K, 0.0)
    if mp <= intrinsic + 0.5 or T <= 1e-10 or mp >= S:
        return None
    sigma = 0.3
    for _ in range(20):
        price = bs_call(S, K, T, sigma)
        diff = price - mp
        sT = math.sqrt(T)
        d1 = (math.log(S / K) + 0.5 * sigma * sigma * T) / (sigma * sT)
        vega = S * sT * math.exp(-d1 * d1 / 2.0) * 0.3989422804014327
        if vega < 1e-10:
            return None
        sigma -= diff / vega
        if sigma <= 0.01:
            sigma = 0.01
        if sigma > 3.0:
            return None
        if abs(diff) < 0.5:
            return sigma
    return None


def get_book(od):
    bids = {p: abs(v) for p, v in od.buy_orders.items()} if od.buy_orders else {}
    asks = {p: abs(v) for p, v in od.sell_orders.items()} if od.sell_orders else {}
    return bids, asks


def best_mid(b, a):

    if not b or not a:
        return None
    return (max(b) + min(a)) / 2.0


def stable_mid(b, a):

    if not b or not a:
        return None
    return (min(b) + max(a)) / 2.0


def wall_mid(b, a):
    return stable_mid(b, a)


def trade_towards(sym, od, cur, tgt):
    orders = []
    if tgt is None or tgt == cur:
        return orders
    if not od.buy_orders or not od.sell_orders:
        return orders
    d = tgt - cur
    if d > 0:
        orders.append(Order(sym, min(od.sell_orders), d))
    else:
        orders.append(Order(sym, max(od.buy_orders), d))
    return orders


class Trader:
    def hydrogel_trade(self, state, hg_ema_adj, history, agg_long, agg_short):

        orders = []
        od = state.order_depths.get("HYDROGEL_PACK")
        if od is None:
            return orders, agg_long, agg_short

        bids, asks = get_book(od)
        mid = stable_mid(bids, asks)
        if mid is None:
            return orders, agg_long, agg_short

        bb = max(bids) if bids else None
        ba = min(asks) if asks else None
        pos = state.position.get("HYDROGEL_PACK", 0)
        limit = LIMITS["HYDROGEL_PACK"]
        bc = limit - pos
        sc = limit + pos

        if pos <= 0:
            agg_long = 0
        else:
            agg_long = min(agg_long, pos)
        if pos >= 0:
            agg_short = 0
        else:
            agg_short = min(agg_short, abs(pos))

        dev = mid - hg_ema_adj

        if dev <= -HG_OU_ENTRY:
            q = min(HG_OU_QTY, bc, asks.get(ba, 0) if ba else 0)
            if q > 0:
                orders.append(Order("HYDROGEL_PACK", ba, q))
                bc -= q
                agg_long += q

        elif dev >= HG_OU_ENTRY:
            q = min(HG_OU_QTY, sc, bids.get(bb, 0) if bb else 0)
            if q > 0:
                orders.append(Order("HYDROGEL_PACK", bb, -q))
                sc -= q
                agg_short += q

        elif agg_long > 0 and dev >= -HG_OU_EXIT:
            q = min(agg_long, sc, bids.get(bb, 0) if bb else 0)
            if q > 0:
                orders.append(Order("HYDROGEL_PACK", bb, -q))
                sc -= q
                agg_long -= q

        elif agg_short > 0 and dev <= HG_OU_EXIT:
            q = min(agg_short, bc, asks.get(ba, 0) if ba else 0)
            if q > 0:
                orders.append(Order("HYDROGEL_PACK", ba, q))
                bc -= q
                agg_short -= q

        if agg_long == 0 and agg_short == 0:
            ltm = sum(history) / len(history) if history else mid
            skewed_fv = (mid - 0.25 * (mid - ltm)) - (0.1 * pos)

            bp = int(round(skewed_fv - HG_MM_SPREAD))
            ap = int(round(skewed_fv + HG_MM_SPREAD))

            if bc > 0:
                orders.append(Order("HYDROGEL_PACK", bp, min(bc, HG_MM_SIZE)))
            if sc > 0:
                orders.append(Order("HYDROGEL_PACK", ap, -min(sc, HG_MM_SIZE)))

        return orders, agg_long, agg_short

    def wallmid_trade(self, state, sym):
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
                q = min(limit - pos, asks[ap])
                if q > 0:
                    orders.append(Order(sym, ap, q))
                    pos += q
            elif ap <= wmid and pos < 0:
                q = min(-pos, asks[ap])
                if q > 0:
                    orders.append(Order(sym, ap, q))
                    pos += q
        for bp in sorted(bids, reverse=True):
            if bp > wmid and pos > -limit:
                q = min(limit + pos, bids[bp])
                if q > 0:
                    orders.append(Order(sym, bp, -q))
                    pos -= q
            elif bp >= wmid and pos > 0:
                q = min(pos, bids[bp])
                if q > 0:
                    orders.append(Order(sym, bp, -q))
                    pos -= q
        if not bids or not asks:
            return orders
        bidp = int(min(bids) + 1)
        askp = int(max(asks) - 1)
        for bp in sorted(bids, reverse=True):
            if bids[bp] > 1 and bp + 1 < wmid:
                bidp = max(bidp, int(bp + 1))
                break
            elif bp < wmid:
                bidp = max(bidp, int(bp))
                break
        for ap in sorted(asks):
            if asks[ap] > 1 and ap - 1 > wmid:
                askp = min(askp, int(ap - 1))
                break
            elif ap > wmid:
                askp = min(askp, int(ap))
                break
        rb = max(0, limit - pos)
        rs = max(0, limit + pos)
        if rb > 0:
            orders.append(Order(sym, bidp, rb))
        if rs > 0:
            orders.append(Order(sym, askp, -rs))
        return orders

    def zone_trade(
        self, state, S, center, sigma, tte, trend_up=False, crash_suppress=False
    ):
        result = {}
        buy_below = center - ZONE_OFF
        sell_above = center + (ZONE_OFF_TREND if trend_up else ZONE_OFF)
        flat_low = center - FLAT_OFF
        flat_high = center + FLAT_OFF

        if S < buy_below:
            zone = 1
        elif S > sell_above:
            zone = -1
        elif flat_low <= S <= flat_high:
            zone = 0
        else:
            zone = None

        if crash_suppress and zone == 1:
            zone = None

        ve_od = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if ve_od:
            cur = state.position.get("VELVETFRUIT_EXTRACT", 0)
            lim = LIMITS["VELVETFRUIT_EXTRACT"]
            tgt = (
                lim
                if zone == 1
                else (-lim if zone == -1 else (0 if zone == 0 else None))
            )
            result["VELVETFRUIT_EXTRACT"] = trade_towards(
                "VELVETFRUIT_EXTRACT", ve_od, cur, tgt
            )

        for sym in ZONE_VOUCHERS:
            od = state.order_depths.get(sym)
            if not od:
                continue
            b, a = get_book(od)
            mid = best_mid(b, a)
            cur = state.position.get(sym, 0)
            lim = LIMITS[sym]
            tgt = (
                lim
                if zone == 1
                else (-lim if zone == -1 else (0 if zone == 0 else None))
            )
            if mid is not None and sigma > 0.05 and tgt is not None:
                K = STRIKES[sym]
                fair = bs_call(S, K, tte, sigma)
                mis = mid - fair
                if zone == 1 and mis > BS_REJECT:
                    tgt = None
                elif zone == -1 and mis < -BS_REJECT:
                    tgt = None
            result[sym] = trade_towards(sym, od, cur, tgt)
        return result

    def run(self, state: TradingState):
        result = {}
        conversions = 0

        saved = {}
        if state.traderData:
            try:
                saved = json.loads(state.traderData)
            except:
                saved = {}

        sigma_ema = saved.get("sig", 0.30)
        ve_ema = saved.get("ve", None)
        day_est = saved.get("d", 0)
        hg_ema = saved.get("hg", None)
        trend_ctr = saved.get("tc", 0)
        last_ts = saved.get("lts", -1)
        crash_cd = saved.get("ccd", 0)
        m38_sig = saved.get("m38", 0.0)
        ve_cp_sig = saved.get("vcp", 0.0)
        agg_long = saved.get("al", 0)
        agg_short = saved.get("as", 0)
        history = saved.get("hist", [])

        ts = state.timestamp

        if ts < last_ts:
            trend_ctr = 0

        S = None
        ve_od = state.order_depths.get("VELVETFRUIT_EXTRACT")
        if ve_od:
            b, a = get_book(ve_od)
            S = best_mid(b, a)

        if S is not None:
            if ve_ema is None:
                ve_ema = 5245.0
            else:
                ve_ema = VE_EMA_ALPHA * S + (1 - VE_EMA_ALPHA) * ve_ema

        hg_od = state.order_depths.get("HYDROGEL_PACK")
        if hg_od:
            hb, ha = get_book(hg_od)
            hg_smid = stable_mid(hb, ha)
            if hg_smid is not None:
                history.append(hg_smid)
                if len(history) > HG_HISTORY:
                    history.pop(0)
                if hg_ema is None:
                    hg_ema = HG_EMA_INIT
                else:
                    hg_ema = HG_EMA_ALPHA * hg_smid + (1 - HG_EMA_ALPHA) * hg_ema

        tte_s = (4 - day_est) / 252.0
        tte_e = (3 - day_est) / 252.0
        frac = ts / 999900.0 if ts < 999900 else 1.0
        tte = tte_s + frac * (tte_e - tte_s)
        if tte <= 0:
            tte = 1e-6

        if S is not None and ve_ema is not None:
            if S > ve_ema + 5:
                trend_ctr = max(1, trend_ctr + 1)
            elif S < ve_ema - 5:
                trend_ctr = min(-1, trend_ctr - 1)
            else:
                if trend_ctr > 0:
                    trend_ctr -= 1
                elif trend_ctr < 0:
                    trend_ctr += 1
        trend_up = trend_ctr >= TREND_TICKS

        vfe_trades = state.market_trades.get("VELVETFRUIT_EXTRACT", [])
        for t in vfe_trades:
            seller = getattr(t, "seller", None) or ""
            buyer = getattr(t, "buyer", None) or ""
            if seller.strip() == "Mark 22" and buyer.strip() == "Mark 49":
                crash_cd = CRASH_COOL
                break
        if crash_cd > 0:
            crash_cd -= 1
        crash_suppress = crash_cd > 0

        m38_sig *= M38_DECAY
        for t in state.market_trades.get("HYDROGEL_PACK", []):
            buyer = (getattr(t, "buyer", None) or "").strip()
            seller = (getattr(t, "seller", None) or "").strip()
            qty = abs(getattr(t, "quantity", 0))
            if buyer == "Mark 38":
                m38_sig -= qty
            elif seller == "Mark 38":
                m38_sig += qty
        m38_sig = max(-M38_MAX / M38_SCALE, min(M38_MAX / M38_SCALE, m38_sig))
        hg_ema_adj = (hg_ema or HG_EMA_INIT) + M38_SCALE * m38_sig

        ve_cp_sig *= VE_CP_DECAY
        for t in vfe_trades:
            buyer = (getattr(t, "buyer", None) or "").strip()
            seller = (getattr(t, "seller", None) or "").strip()
            qty = abs(getattr(t, "quantity", 0))
            if buyer in VE_CP_WEIGHTS:
                ve_cp_sig += VE_CP_WEIGHTS[buyer] * qty
            if seller in VE_CP_WEIGHTS:
                ve_cp_sig -= VE_CP_WEIGHTS[seller] * qty
        ve_cp_sig = max(
            -VE_CP_MAX / VE_CP_SCALE, min(VE_CP_MAX / VE_CP_SCALE, ve_cp_sig)
        )
        ve_ema_adj = (ve_ema or 5245.0) + VE_CP_SCALE * ve_cp_sig

        if S is not None and S > 0:
            ivs = []
            for sym in ATM_STRIKES:
                od = state.order_depths.get(sym)
                if not od:
                    continue
                b2, a2 = get_book(od)
                m = best_mid(b2, a2)
                if m is None:
                    continue
                iv = bs_iv(m, S, STRIKES[sym], tte)
                if iv and 0.05 < iv < 2.0:
                    ivs.append(iv)
            if ivs:
                sigma_ema = (
                    VOL_ALPHA * (sum(ivs) / len(ivs)) + (1 - VOL_ALPHA) * sigma_ema
                )

        try:
            hg_orders, agg_long, agg_short = self.hydrogel_trade(
                state, hg_ema_adj, history, agg_long, agg_short
            )
            result["HYDROGEL_PACK"] = hg_orders
        except:
            result["HYDROGEL_PACK"] = []

        if S is not None and ve_ema is not None:
            try:
                r = self.zone_trade(
                    state, S, ve_ema_adj, sigma_ema, tte, trend_up, crash_suppress
                )
                result.update(r)
            except:
                pass

        try:
            result["VEV_4000"] = self.wallmid_trade(state, "VEV_4000")
        except:
            result["VEV_4000"] = []

        td = json.dumps(
            {
                "sig": sigma_ema,
                "ve": ve_ema,
                "d": day_est,
                "hg": hg_ema,
                "tc": trend_ctr,
                "lts": ts,
                "ccd": crash_cd,
                "m38": m38_sig,
                "vcp": ve_cp_sig,
                "al": agg_long,
                "as": agg_short,
                "hist": history,
            }
        )
        return result, conversions, td
