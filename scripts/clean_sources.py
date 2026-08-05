#!/usr/bin/env python3

import argparse
import ast
import io
import tokenize
from pathlib import Path


DOCUMENTED_NODES = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
PROTECTED_COMMENT_MARKERS = (
    "#!",
    "# -*- coding",
    "# coding:",
    "# SPDX-",
    "# type:",
    "# noqa",
    "# fmt:",
    "# ruff:",
    "# pyright:",
)


def has_docstring(node: ast.AST) -> bool:
    body = getattr(node, "body", None)
    if not body:
        return False
    first = body[0]
    return (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    )


def docstring_spans(tree: ast.AST) -> list[tuple[int, int, bool, int]]:
    spans = []
    for node in ast.walk(tree):
        if not isinstance(node, DOCUMENTED_NODES) or not has_docstring(node):
            continue
        statement = node.body[0]
        spans.append(
            (
                statement.lineno,
                statement.end_lineno,
                len(node.body) == 1 and not isinstance(node, ast.Module),
                statement.col_offset,
            )
        )
    return sorted(spans, reverse=True)


class RemoveDocstrings(ast.NodeTransformer):
    def _clean_body(self, node: ast.AST) -> ast.AST:
        if has_docstring(node):
            node.body = node.body[1:]
        if not node.body and not isinstance(node, ast.Module):
            node.body = [ast.Pass()]
        return self.generic_visit(node)

    def visit_Module(self, node: ast.Module) -> ast.AST:
        return self._clean_body(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> ast.AST:
        return self._clean_body(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        return self._clean_body(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        return self._clean_body(node)


def normalized_tree(source: str) -> str:
    tree = ast.parse(source)
    tree = RemoveDocstrings().visit(tree)
    ast.fix_missing_locations(tree)
    return ast.dump(tree, include_attributes=False)


def strip_docstrings(source: str) -> str:
    tree = ast.parse(source)
    lines = source.splitlines(keepends=True)
    for start, end, needs_pass, indentation in docstring_spans(tree):
        replacement = " " * indentation + "pass\n" if needs_pass else "\n"
        lines[start - 1 : end] = [replacement] + ["\n"] * (end - start)
    return "".join(lines)


def strip_comments(source: str) -> str:
    tokens = []
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.COMMENT:
            if token.string.startswith(PROTECTED_COMMENT_MARKERS):
                raise ValueError(
                    f"refusing to remove protected directive: {token.string}"
                )
            token = tokenize.TokenInfo(
                token.type, "", token.start, token.end, token.line
            )
        tokens.append(token)
    return tokenize.untokenize(tokens)


def clean(source: str) -> str:
    expected = normalized_tree(source)
    cleaned = strip_comments(strip_docstrings(source))
    if not cleaned.endswith("\n"):
        cleaned += "\n"
    actual = normalized_tree(cleaned)
    if actual != expected:
        raise ValueError("cleaning changed the executable syntax tree")
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    changed = False
    for path in args.paths:
        source = path.read_text(encoding="utf-8")
        cleaned = clean(source)
        if cleaned == source:
            continue
        changed = True
        if not args.check:
            path.write_text(cleaned, encoding="utf-8")
        print(path)
    return int(args.check and changed)


if __name__ == "__main__":
    raise SystemExit(main())
