#!/usr/bin/env python3

import ast
import io
import json
import tokenize
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def verify_source(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    comments = [
        token
        for token in tokenize.generate_tokens(io.StringIO(source).readline)
        if token.type == tokenize.COMMENT
    ]
    docstrings = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            if ast.get_docstring(node, clean=False) is not None:
                docstrings.append(node)
    if comments or docstrings:
        raise ValueError(
            f"{path}: found {len(comments)} comments and {len(docstrings)} docstrings"
        )


def main() -> int:
    traders = sorted(ROOT.glob("rounds/round-*/trader.py"))
    summaries = sorted(ROOT.glob("rounds/round-*/summary.json"))
    if len(traders) != 5:
        raise ValueError(f"expected 5 traders, found {len(traders)}")
    if len(summaries) != 5:
        raise ValueError(f"expected 5 summaries, found {len(summaries)}")
    for trader in traders:
        verify_source(trader)
    for summary in summaries:
        json.loads(summary.read_text(encoding="utf-8"))
    print("verified 5 comment-free strategies and 5 result summaries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
