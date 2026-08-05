# Data and capsule provenance

## Two different meanings of "capsule"

The supplied `Round_1.zip` through `Round_5.zip` files are submission-result exports. Each contains:

- the submitted Python strategy;
- a result JSON with status, P&L, activity CSV, graph CSV, and ending positions; and
- a JSON-formatted log with submission ID, tick logs, the duplicated activity CSV, and trade history.

Historical Prosperity data capsules are different: they normally contain `prices_round_*_day_*.csv` and `trades_round_*_day_*.csv` files for research and backtesting.

## What is tracked here

| Artifact | Local workspace | Git repository | Reason |
|---|---:|---:|---|
| Cleaned `trader.py` files | Yes | Yes | User-owned strategy snapshots |
| Sanitized `summary.json` files | Yes | Yes | Aggregate metrics without submission UUIDs |
| Generated SVG figures | Yes | Yes | Aggregate result visualization |
| Raw result/log JSON | Yes | No | Identifiers, organizer data, and large duplicated payloads |
| Original ZIP exports | Outside project | No | Immutable source archive |
| Public historical CSV capsules | No | No | Provenance and redistribution rights are unclear |

Each tracked summary stores the byte length and SHA-256 digest of its two local raw inputs. That keeps the audit traceable without transferring the inputs to GitHub.

## Public historical-data references

An unofficial backtester mirror currently exposes complete-looking Round 1–5 price/trade resources at commit `0094c681f8cd019889761e6431a1a47ea151aaa8`:

- [Round 1 resources](https://github.com/nabayansaha/imc-prosperity-4-backtester/tree/0094c681f8cd019889761e6431a1a47ea151aaa8/prosperity4bt/resources/round1)
- [Round 2 resources](https://github.com/nabayansaha/imc-prosperity-4-backtester/tree/0094c681f8cd019889761e6431a1a47ea151aaa8/prosperity4bt/resources/round2)
- [Round 3 resources](https://github.com/nabayansaha/imc-prosperity-4-backtester/tree/0094c681f8cd019889761e6431a1a47ea151aaa8/prosperity4bt/resources/round3)
- [Round 4 resources](https://github.com/nabayansaha/imc-prosperity-4-backtester/tree/0094c681f8cd019889761e6431a1a47ea151aaa8/prosperity4bt/resources/round4)
- [Round 5 resources](https://github.com/nabayansaha/imc-prosperity-4-backtester/tree/0094c681f8cd019889761e6431a1a47ea151aaa8/prosperity4bt/resources/round5)

The backtester code is MIT-licensed, but the mirror does not separately establish that the organizer-origin CSV data is covered by that license. A link is therefore included for provenance; the CSVs are not copied into this repository.

Before downloading, republishing, or transferring competition data, review the current [IMC Prosperity terms](https://prosperity.imc.com/docs/terms-and-conditions.pdf) and [legal/privacy notice](https://prosperity.imc.com/docs/privacy-policy.pdf), and obtain permission where required. A private GitHub repository is still a transfer to a third-party service.

## Restoring local result exports

The project expects the following untracked paths when regenerating summaries or figures:

```text
rounds/round-01/capsule/result.json
rounds/round-01/capsule/submission.log.json
...
rounds/round-05/capsule/result.json
rounds/round-05/capsule/submission.log.json
```

The current workspace already contains these files. On another machine, extract each personal submission export locally and rename the result and log files to this convention. Do not commit them accidentally; `.gitignore` covers all ten paths.
