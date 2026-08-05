# Round 3 — building a multi-product derivatives portfolio

[← Repository overview](../../README.md) · [Cleaned strategy](trader.py) · [Machine-readable result](summary.json) · [Full results](../../docs/results.md#round-3)

| Final score | Products | Fill events | Filled units | Largest contributor |
|---:|---:|---:|---:|---|
| **33,767.52** | 12 | 4,026 | 25,817 | Hydrogel: 27,719.00 |

![Round 3 product contribution](../../docs/assets/product-pnl-round-03.svg)

## The portfolio design

Round 3 expanded the book from two products to two core markets plus ten Velvetfruit vouchers. That changed the research question from “what is this product worth?” to “how should several related products be valued and risk-managed together?”

I split the system into five models rather than searching for one formula that covered every strike.

## 1. Hydrogel Pack — slow mean reversion

### Observation and hypothesis

Hydrogel appeared to oscillate around a stable long-run level. I used an initial fair value near 9,985 and allowed only an ultra-slow EMA adjustment, which reflects a belief that short-term moves were more likely deviations than permanent repricing.

### Implementation

The strategy opened 20-unit lots when the midpoint moved at least 40 ticks from fair and closed as the deviation normalized. Exposure was capped at 200 units. The wide threshold deliberately traded fewer, stronger deviations.

## 2. Velvetfruit Extract — directional mean reversion

Velvetfruit used the same basic idea around a center near 5,249, but with a 20-tick entry threshold and a lower directional cap. This underlying also became the hedge instrument for the voucher portfolio.

## 3. Deep in-the-money vouchers — wall midpoint

`VEV_4000` and `VEV_4500` used the midpoint of the outer visible bid and ask levels rather than the top-of-book midpoint. The working hypothesis was that persistent deeper liquidity represented fair value more reliably when the best quotes were flickering or strategic.

The engine crossed prices through that wall midpoint and used the remaining capacity for passive market making. `VEV_4500` also had a parity check based on the deep-in-the-money approximation `voucher ≈ underlying − strike`.

## 4. VEV 5000–5500 — locally linear fair value

For the middle strikes, the code models voucher value as:

```text
fair voucher value = calibrated delta × Velvetfruit price + calibrated offset
```

Each strike has its own delta, offset, opening threshold, and closing threshold. Order size grows with absolute mispricing, bounded between 5 and 40 units. New short exposure is capped at 250, and volume scales down near the end of the round.

This is not a full option-pricing model. It is a local empirical approximation: within the observed price region, a straight line can be easier to calibrate and more robust than estimating every option parameter under time pressure.

## 5. Portfolio delta hedge

The strategy sums Velvetfruit inventory and voucher inventory weighted by estimated deltas. It hedges with Velvetfruit only after total delta becomes extreme, targeting a smaller—but not zero—residual. That makes the hedge a last-resort risk control rather than a constant source of transaction cost.

## What happened live

The strongest contributions came from the core products and the locally calibrated `VEV_5000` model.

| Group | Final P&L | Interpretation |
|---|---:|---|
| Hydrogel | 27,719.00 | Strongest mean-reversion contributor |
| Velvetfruit | 14,130.00 | Profitable core/hedge product |
| `VEV_5000` | 22,446.63 | Best voucher calibration |
| `VEV_4000` + `VEV_4500` | 4,704.03 | Small positive wall-mid contribution |

The round finished at 33,767.52 after reaching 74,019.89 near timestamp 950,000, demonstrating that the portfolio could generate meaningful edge across both spot and voucher products.

## What I learned

- Local linear voucher models can be effective when calibrated separately by strike.
- Outer-book structure can provide a useful alternative to a flickering top-of-book midpoint.
- Portfolio delta is a practical shared risk language across an underlying and its vouchers.
- Entry, exit, and end-of-round behavior should be designed as one coordinated lifecycle.

Round 4 kept the multi-product structure but made fair value more stable, added informed-flow signals, and used a volatility surface as a consistency filter.
