"""The prose that describes the published data, for the docs gates.

tests/test_no_data_numbers.py and tests/test_no_stale_dates.py read the same
documents:

- the repository README.md and AGENTS.md
- every Markdown file under catalog/
- the ``description`` of the root Catalog and of every Collection

Fenced code blocks are removed. A query may name a date or a number, and
tests/test_queries.py runs every query against the published data.

This module is a helper, not a gate. tests/run_all.py does not run it.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
FENCE = re.compile(r"```.*?```", re.S)


def documents() -> list[tuple[Path, str]]:
    """Each document and its prose, with fenced code blocks removed."""
    paths = [ROOT / "README.md", ROOT / "AGENTS.md"]
    paths += sorted(CATALOG.glob("**/*.md"))
    docs = [(p, p.read_text()) for p in paths]
    for path in [CATALOG / "catalog.json"] + sorted(CATALOG.glob("*/collection.json")):
        docs.append((path, json.loads(path.read_text()).get("description", "")))
    # Keep the newlines of each fence, so line numbers match the file.
    return [(path, FENCE.sub(lambda m: "\n" * m.group(0).count("\n"), text))
            for path, text in docs]


def collections() -> list[dict]:
    """Every Collection document under catalog/."""
    return [json.loads(p.read_text()) for p in sorted(CATALOG.glob("*/collection.json"))]
