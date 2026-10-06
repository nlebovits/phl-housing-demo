#!/usr/bin/env python3
"""Check a collection's map styles against a new extract before it publishes.

Every ``match`` branch and ``step`` class in ``catalog/<coll>/styles/*.json``
was verified against the data when the catalog shipped (AGENTS.md, "Styles
are verified against the data"). A refresh can break that in three ways, and
each one fails the check:

- A styled column is gone from the new data.
- A ``match`` label, or a ``step`` class, matches no row. The legend then
  lists a category the map never paints.
- A value appears that the previous version did not have and no ``match``
  branch names. Those features paint with the fallback colour while the
  legend has no entry for them.

Values that fell to the fallback before the refresh are left alone. Several
styles name only the categories they highlight on purpose (vacant-parcels
names codes 91 and 92 and greys the rest).

    python3 tools/check_styles.py land_use new.parquet [previous.parquet]
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"


@dataclass
class Rule:
    style: str
    kind: str  # "match" or "step"
    column: str
    labels: list = field(default_factory=list)  # match labels, flattened
    stops: list = field(default_factory=list)  # step boundaries


def walk(node, style: str, rules: list[Rule]) -> None:
    """Collect every match/step on a ["get", column] input, at any depth."""
    if not isinstance(node, list):
        if isinstance(node, dict):
            for value in node.values():
                walk(value, style, rules)
        return
    if (
        len(node) >= 3
        and node[0] in ("match", "step")
        and isinstance(node[1], list)
        and len(node[1]) == 2
        and node[1][0] == "get"
    ):
        column = node[1][1]
        if node[0] == "match":
            labels = []
            for label in node[2:-1:2]:
                labels.extend(label if isinstance(label, list) else [label])
            rules.append(Rule(style, "match", column, labels=labels))
        else:
            rules.append(Rule(style, "step", column, stops=list(node[3::2])))
    for child in node:
        walk(child, style, rules)


def style_rules(collection: str, catalog: Path = CATALOG) -> list[Rule]:
    rules: list[Rule] = []
    for path in sorted((catalog / collection / "styles").glob("*.json")):
        style = json.loads(path.read_text())
        for layer in style.get("layers", []):
            for key in ("paint", "layout", "filter"):
                walk(layer.get(key), path.name, rules)
    return rules


def distinct_counts(con, path: str, column: str) -> dict:
    rows = con.execute(
        f'SELECT "{column}", count(*) FROM read_parquet(?) GROUP BY 1', [path]
    ).fetchall()
    return {value: count for value, count in rows if value is not None}


def columns(con, path: str) -> set[str]:
    rows = con.execute("SELECT name FROM parquet_schema(?)", [path]).fetchall()
    return {name for (name,) in rows}


def same(a, b) -> bool:
    """Equality the way MapLibre compares a match label with a value."""
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return float(a) == float(b)
    return a == b


def check(collection: str, new: str, previous: str | None = None,
          catalog: Path = CATALOG) -> list[str]:
    """Every problem the new data causes in the collection's styles."""
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    problems: list[str] = []
    present = columns(con, new)
    old_present = columns(con, previous) if previous else set()

    for rule in style_rules(collection, catalog):
        where = f"{rule.style}: {rule.kind} on {rule.column}"
        if rule.column not in present:
            problems.append(f"{where}: the column is gone from the new data")
            continue
        counts = distinct_counts(con, new, rule.column)

        if rule.kind == "match":
            for label in rule.labels:
                if not any(same(label, value) for value in counts):
                    problems.append(f"{where}: branch {label!r} matches no row")
            if previous and rule.column in old_present:
                before = distinct_counts(con, previous, rule.column)
                for value, count in sorted(counts.items(), key=lambda kv: str(kv[0])):
                    named = any(same(value, label) for label in rule.labels)
                    seen = any(same(value, old) for old in before)
                    if not named and not seen:
                        problems.append(
                            f"{where}: new value {value!r} ({count} rows) "
                            "has no branch and paints with the fallback"
                        )
        else:
            edges = [float("-inf")] + [float(s) for s in rule.stops] + [float("inf")]
            for low, high in zip(edges, edges[1:]):
                hits = sum(c for v, c in counts.items() if low <= float(v) < high)
                if hits == 0:
                    problems.append(f"{where}: class [{low}, {high}) holds no row")
    return problems


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("collection")
    parser.add_argument("new")
    parser.add_argument("previous", nargs="?")
    args = parser.parse_args()
    found = check(args.collection, args.new, args.previous)
    for problem in found:
        print(f"FAIL {args.collection}/{problem}")
    if found:
        raise SystemExit(1)
    print(f"OK: {len(style_rules(args.collection))} style rule(s) hold "
          f"for {args.collection}")
