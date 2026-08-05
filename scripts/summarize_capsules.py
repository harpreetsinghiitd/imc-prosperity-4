#!/usr/bin/env python3

import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fingerprint(path: Path) -> dict[str, int | str]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"bytes": path.stat().st_size, "sha256": digest.hexdigest()}


def parse_activity(
    csv_text: str,
) -> tuple[dict[str, dict[str, str]], dict[str, object]]:
    latest = {}
    days = set()
    timestamps = set()
    row_count = 0
    for row in csv.DictReader(io.StringIO(csv_text), delimiter=";"):
        row_count += 1
        days.add(int(row["day"]))
        timestamp = int(row["timestamp"])
        timestamps.add(timestamp)
        latest[row["product"]] = row
    coverage = {
        "activity_rows": row_count,
        "days": sorted(days),
        "timestamp_start": min(timestamps),
        "timestamp_end": max(timestamps),
        "timestamp_count": len(timestamps),
    }
    return latest, coverage


def parse_fills(
    trades: list[dict[str, object]],
) -> tuple[dict[str, dict[str, int]], dict[str, int | None]]:
    totals = defaultdict(lambda: {"events": 0, "buy_volume": 0, "sell_volume": 0})
    timestamps = []
    for trade in trades:
        buyer = trade.get("buyer")
        seller = trade.get("seller")
        if buyer != "SUBMISSION" and seller != "SUBMISSION":
            continue
        product = str(trade["symbol"])
        quantity = int(trade["quantity"])
        timestamps.append(int(trade["timestamp"]))
        totals[product]["events"] += 1
        if buyer == "SUBMISSION":
            totals[product]["buy_volume"] += quantity
        if seller == "SUBMISSION":
            totals[product]["sell_volume"] += quantity
    coverage = {
        "timestamp_start": min(timestamps) if timestamps else None,
        "timestamp_end": max(timestamps) if timestamps else None,
    }
    return totals, coverage


def graph_summary(csv_text: str) -> dict[str, object]:
    rows = [
        {"timestamp": int(row["timestamp"]), "value": float(row["value"])}
        for row in csv.DictReader(io.StringIO(csv_text), delimiter=";")
    ]
    by_timestamp = {row["timestamp"]: row["value"] for row in rows}
    minimum = min(rows, key=lambda row: row["value"])
    maximum = max(rows, key=lambda row: row["value"])
    return {
        "points": len(rows),
        "timestamp_start": rows[0]["timestamp"],
        "timestamp_end": rows[-1]["timestamp"],
        "checkpoints": {
            str(timestamp): by_timestamp[timestamp]
            for timestamp in (0, 250000, 500000, 750000, 998000)
        },
        "minimum": minimum,
        "maximum": maximum,
    }


def summarize(round_dir: Path) -> dict[str, object]:
    result_path = round_dir / "capsule" / "result.json"
    log_path = round_dir / "capsule" / "submission.log.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    log = json.loads(log_path.read_text(encoding="utf-8"))

    if result["activitiesLog"] != log["activitiesLog"]:
        raise ValueError(f"{round_dir}: activity logs do not match")

    latest, coverage = parse_activity(result["activitiesLog"])
    fills, fill_coverage = parse_fills(log["tradeHistory"])
    ending_positions = {
        str(item["symbol"]): int(item["quantity"]) for item in result["positions"]
    }
    products = []
    for symbol in sorted(latest):
        fill = fills.get(symbol, {"events": 0, "buy_volume": 0, "sell_volume": 0})
        products.append(
            {
                "symbol": symbol,
                "final_profit": float(latest[symbol]["profit_and_loss"]),
                "ending_position": ending_positions.get(symbol, 0),
                "fill_events": fill["events"],
                "buy_volume": fill["buy_volume"],
                "sell_volume": fill["sell_volume"],
            }
        )

    final_score = float(result["profit"])
    return {
        "round": int(result["round"]),
        "status": result["status"],
        "final_score": final_score,
        "coverage": coverage,
        "graph": graph_summary(result["graphLog"]),
        "all_trade_events": len(log["tradeHistory"]),
        "submission_fill_events": sum(item["fill_events"] for item in products),
        "submission_fill_volume": sum(
            item["buy_volume"] + item["sell_volume"] for item in products
        ),
        "submission_fill_coverage": fill_coverage,
        "tick_log_records": len(log["logs"]),
        "products": products,
        "ending_positions": dict(sorted(ending_positions.items())),
        "source_files": {
            "result.json": fingerprint(result_path),
            "submission.log.json": fingerprint(log_path),
        },
    }


def main() -> int:
    for round_dir in sorted(ROOT.glob("rounds/round-*")):
        output = round_dir / "summary.json"
        output.write_text(
            json.dumps(summarize(round_dir), indent=2, sort_keys=False) + "\n",
            encoding="utf-8",
        )
        print(output.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
