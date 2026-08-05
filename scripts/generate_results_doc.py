#!/usr/bin/env python3

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def number(value: float) -> str:
    return f"{value:,.2f}"


def integer(value: int) -> str:
    return f"{value:,}"


def main() -> int:
    summaries = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(ROOT.glob("rounds/round-*/summary.json"))
    ]
    final_total = sum(item["final_score"] for item in summaries)
    lines = [
        "# Results and capsule validation",
        "",
        "This report is generated from the sanitized `summary.json` file in each round. The local raw submission exports were used to build those summaries, but are deliberately excluded from Git.",
        "",
        "## Overall results",
        "",
        "| Round | Status | Final score | Products | Fills | Filled units |",
        "|---:|---|---:|---:|---:|---:|",
    ]
    for item in summaries:
        lines.append(
            "| {round} | {status} | {score} | {products} | {fills} | {volume} |".format(
                round=item["round"],
                status=item["status"],
                score=number(item["final_score"]),
                products=len(item["products"]),
                fills=integer(item["submission_fill_events"]),
                volume=integer(item["submission_fill_volume"]),
            )
        )
    lines.extend(
        [
            f"| **Total** |  | **{number(final_total)}** |  | **{integer(sum(item['submission_fill_events'] for item in summaries))}** | **{integer(sum(item['submission_fill_volume'] for item in summaries))}** |",
            "",
            "Each final score is the `profit` value recorded in the supplied result export.",
            "",
            "![Final scores by round](assets/round-profits.svg)",
            "",
            "## P&L progression",
            "",
            "The exported graph stops at timestamp 998,000, while the reported final result uses timestamp 999,900.",
            "",
            "| Round | 0 | 250k | 500k | 750k | 998k | Reported final |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in summaries:
        graph = item["graph"]
        checkpoints = graph["checkpoints"]
        lines.append(
            "| {round} | {start} | {q1} | {half} | {q3} | {end} | {final} |".format(
                round=item["round"],
                start=number(checkpoints["0"]),
                q1=number(checkpoints["250000"]),
                half=number(checkpoints["500000"]),
                q3=number(checkpoints["750000"]),
                end=number(checkpoints["998000"]),
                final=number(item["final_score"]),
            )
        )
    lines.extend(
        [
            "",
            "![P&L curves for all five rounds](assets/pnl-curves.svg)",
            "",
            "## Product-level contribution",
            "",
            "A fill event is one trade-history record where the submission is the buyer or seller. Ending positions were checked against signed fill quantities.",
        ]
    )
    for item in summaries:
        round_number = item["round"]
        lines.extend(
            [
                "",
                f"### Round {round_number}",
                "",
                f"![Round {round_number} product P&L](assets/product-pnl-round-{round_number:02}.svg)",
                "",
                "| Product | Final P&L | End position | Fill events | Buy units | Sell units |",
                "|---|---:|---:|---:|---:|---:|",
            ]
        )
        for product in item["products"]:
            lines.append(
                "| `{symbol}` | {profit} | {position} | {events:,} | {buy:,} | {sell:,} |".format(
                    symbol=product["symbol"],
                    profit=number(product["final_profit"]),
                    position=product["ending_position"],
                    events=product["fill_events"],
                    buy=product["buy_volume"],
                    sell=product["sell_volume"],
                )
            )
    lines.extend(
        [
            "",
            "## Validation method",
            "",
            "- Each result and log copy of the embedded activity CSV matched byte-for-byte.",
            "- The final per-product P&L values sum exactly to the result-level P&L in every round.",
            "- Signed submission fills reproduce every ending product position.",
            "- Fill cash flow reproduces the ending XIRECS position.",
            "- Products missing from an ending-position array were treated as flat only after confirming zero net fills.",
            "",
            "The checksums and exact machine-readable metrics live in each round's `summary.json`.",
            "",
        ]
    )
    output = ROOT / "docs" / "results.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines), encoding="utf-8")
    print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
