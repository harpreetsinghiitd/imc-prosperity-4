# Research and documentation methodology

This write-up is designed to answer four questions for every round:

1. What market behavior did I appear to observe?
2. What hypothesis did I encode because of that observation?
3. Why did the chosen valuation and execution logic fit that hypothesis?
4. What did the live result confirm, reject, or leave unresolved?

## Evidence levels

Not every part of a historical strategy reveals the original thought process equally well. The documentation uses three evidence levels:

| Level | Meaning | Example |
|---|---|---|
| Direct implementation evidence | The executable code unambiguously performs the behavior | Osmium shifts quotes once absolute inventory crosses 40 or 60 |
| Direct result evidence | The value is measured from the supplied result/log export | Pepper Root ended Round 1 at +79,403 XIRECS |
| Working hypothesis | The rationale is inferred from the structure and parameters | A slow EMA was intended to avoid chasing noise in a mean-reverting product |

The round narratives use first-person language because they are written for the repository owner, but inference is never presented as a recovered quote or certainty.

## How the source was cleaned

The five original Python files contained 520 tokenizer comments and 26 leading module/class/function docstrings in total. The cleanup process:

1. parsed the original source;
2. removed comments and leading documentation strings;
3. formatted the result consistently;
4. compared the executable abstract syntax tree with the original after normalizing away docstrings; and
5. compiled every cleaned file.

The comparison was exact for all five rounds. A separate differential check ran six realistic sequential activity snapshots per round and observed identical orders and `traderData` before and after cleanup. This establishes behavior preservation for the transformation, not correctness of the underlying strategy.

Protected directives such as encoding cookies, SPDX identifiers, type comments, linter suppressions, and formatter directives were absent from this corpus. The cleanup script refuses to remove those markers if it encounters them in future inputs.

## How the capsule results were audited

For each round, the result export supplied:

- a final status and final score;
- a semicolon-delimited activity log embedded in JSON;
- a sampled P&L graph; and
- ending positions.

The submission log supplied:

- the same embedded activity log;
- 10,000 tick-level log records; and
- trade history with submission-side fills.

The audit verified that:

- both copies of the activity log were identical;
- the last product P&Ls summed exactly to the result-level total;
- signed fills reconstructed every ending product position;
- fill cash flow reconstructed ending XIRECS; and
- flat products omitted from the position array had zero net fills.

The published final score for every round is the `profit` value stored in its result export.

## Why the historical code was preserved

The purpose of this archive is to keep a one-to-one relationship between the submitted artifacts, the capsule outcomes, and the written explanation. Strategy improvements belong in a new research version so the historical record remains reproducible.

The safer workflow is two-track:

```text
historical branch: exact behavior + cleaned presentation + audited results
research branch:   new hypotheses + tests + simplified state + new backtests
```

This repository currently implements the historical track.

## Runtime boundaries

- Python 3.10 or newer is required because Round 2 evaluates a union type annotation at import time.
- Rounds 1–4 depend on the official `datamodel` module.
- Round 2 assumes a persistent `Trader` instance across ticks.
- A complete replay should cover empty and one-sided books, state decoding, independent buy/sell capacity, timestamp boundaries, and serialized state size.
- No financial-performance claim extends beyond the supplied capsule run.
