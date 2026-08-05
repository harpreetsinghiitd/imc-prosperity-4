# Round 2 — richer microstructure and adaptive execution

[← Repository overview](../../README.md) · [Cleaned strategy](trader.py) · [Machine-readable result](summary.json) · [Full results](../../docs/results.md#round-2)

| Final score | Products | Fill events | Filled units | End timestamp |
|---:|---:|---:|---:|---:|
| **96,567.54** | 2 | 1,175 | 6,321 | 999,900 |

![Round 2 product contribution](../../docs/assets/product-pnl-round-02.svg)

## What I wanted to improve

Round 1 showed that the two-product split worked, but both strategies were still built around strong priors: a recognizable book signature for Osmium and a fixed linear path for Pepper Root. My Round 2 code tries to make both systems more data-responsive.

The research direction was:

- replace a single Osmium fair-value heuristic with a slower state estimate plus microstructure-aware execution; and
- replace Pepper Root's fixed slope with an online trend and a more selective way to buy dips and sell strength.

## Ash Coated Osmium

### Working hypothesis

Osmium still mean-reverted, but the best execution decision depended on current variance, inventory, visible queue shape, and proximity to the estimated center. A slow fair-value estimate should avoid chasing transient prices while the order layer reacted faster.

### Valuation

The executable fair value is a slow EMA initialized at 10,000 and updated with `alpha = 0.01`. This gave the execution layer a deliberately stable center while faster book features handled short-lived changes.

### Execution

The Osmium order engine combines:

- microprice variance over a 20-observation window;
- tiered inventory penalties and reservation prices;
- aggressive taking when visible prices cross those reservations;
- near-fair, position-aware taking to reduce unwanted exposure;
- detection of a characteristic top-of-book participant; and
- one- or two-level passive quotes with late-round inventory flattening.

This is a shift from “estimate fair, then quote” to “estimate fair, then condition execution on the current state.”

## Intarian Pepper Root

### Working hypothesis

Pepper Root still rewarded long exposure, but a fitted trend could distinguish an ordinary high price from a price that was high relative to its own path. Short-term pullbacks and order-book pressure could then determine how aggressively to acquire inventory.

### Valuation

The strategy maintains a 500-observation rolling least-squares trend. Its fair-value calculation combines:

1. a forward projection from that trend;
2. a microprice/deep-order-book-imbalance adjustment;
3. an inventory penalty around a target position of +80; and
4. a pullback bonus when price falls below a short reference.

### Execution

- Cheap asks are swept across multiple levels, with deeper dips receiving more aggressive tolerance.
- Remaining buy capacity is split into a passive ladder instead of a single all-or-nothing quote.
- Candidate sell quotes are scored by estimated edge times fill probability.
- Inventory urgency is asymmetric: being below the +80 target is penalized more heavily than being above it.

The goal was not simply to trade more. It was to spend aggressiveness where the trend, pullback, and book pressure agreed.

## What happened live

| Product | Final product P&L | End position | Fill events | Filled units |
|---|---:|---:|---:|---:|
| `ASH_COATED_OSMIUM` | 19,007.54 | 3 | 719 | 4,021 |
| `INTARIAN_PEPPER_ROOT` | 77,560.00 | 80 | 456 | 2,300 |

The product contribution looked remarkably similar to Round 1: Pepper Root generated about 80% of round P&L and Osmium about 20%. The difference was execution intensity—Pepper Root went from eight fills to 456 while still ending at +80.

The P&L path reached 96,410.09 at timestamp 998,000 and finished at **96,567.54 XIRECS**.

## What I carried into Round 3

Round 2 reinforced product-specific modeling and richer execution, but Round 3 changed the shape of the problem. The next challenge was no longer just estimating two spot products independently; it required relating an underlying, multiple vouchers, portfolio delta, and expiry-aware risk.
