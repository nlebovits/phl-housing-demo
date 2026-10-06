#!/usr/bin/env python3
"""The docs quote no counts or percentages measured from the data.

The data changes on every refresh, so a count or a percentage in the
repository README, a catalog README or AGENTS.md, or a Collection
description goes stale. The docs describe what
the data holds and give queries. The current row count is `table:row_count`
in each `collection.json`.

This gate fails on a thousands-separated number (608,085) or a percentage
(94%) outside a code block. It cannot recognise a small count written as
"37 rows", so review those by hand. ALLOWED lists the few numbers that are
configuration, not data.

Run: python3 tests/test_no_data_numbers.py
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"

PATTERN = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?!\w)|\d+(?:\.\d+)?%")
FENCE = re.compile(r"```.*?```", re.S)

# Configuration and definitions, not measurements of the data.
ALLOWED = {
    "200,000",  # tippecanoe's per-tile feature limit
}

errors = []
texts = [(p, p.read_text()) for p in [ROOT / "README.md"] + sorted(CATALOG.glob("**/*.md"))]
texts += [(p, json.loads(p.read_text()).get("description", ""))
          for p in sorted(CATALOG.glob("*/collection.json"))]

for path, text in texts:
    prose = FENCE.sub("", text)
    for match in PATTERN.finditer(prose):
        if match.group(0) in ALLOWED:
            continue
        line = prose[:match.start()].count("\n") + 1
        errors.append(f"{path.relative_to(ROOT)}:{line}: {match.group(0)}")

if errors:
    print("\n".join(f"error  data number in the docs: {e}" for e in errors))
    raise SystemExit(1)
print(f"OK: no data counts or percentages in {len(texts)} document(s)")
