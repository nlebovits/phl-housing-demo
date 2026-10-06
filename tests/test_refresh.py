#!/usr/bin/env python3
"""The refresh pipeline's offline contract.

Three parts of tools/refresh.py decide what a reader later sees, and each one
is checked here without network access:

- ``decide``: a collection is due only when the source edited its rows after
  the current version, and only after ``min_days``.
- ``check_styles.check``: a missing column, an empty match branch, an empty
  step class, or a new unstyled value each fail.
- ``stac_versions``: the Collection's current asset points at
  ``<coll>.parquet``. A new version moves the previous one to an archive
  asset at ``versions/<version>.parquet`` with its checksum intact.

Needs pyarrow and duckdb.

Run: python3 tests/test_refresh.py
"""
import json
import sys
import tempfile
from datetime import datetime, timezone
from importlib.util import find_spec
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

errors: list[str] = []


def check(condition: bool, message: str) -> None:
    if not condition:
        errors.append(message)


missing = [m for m in ("duckdb", "pyarrow") if find_spec(m) is None]
if missing:
    print(f"error  {', '.join(missing)} not installed; this gate checks nothing")
    print("       pip install -r tools/requirements-refresh.txt")
    raise SystemExit(1)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

import check_styles  # noqa: E402
import stac_versions as stac  # noqa: E402
from arcgis import SourceState  # noqa: E402
from refresh import decide  # noqa: E402

# --- decide -------------------------------------------------------------
NOW = datetime(2026, 10, 20, 7, 0, tzinfo=timezone.utc)
WEEKLY = {"min_days": 7}


def probe(edited: str) -> SourceState:
    return SourceState("x", "u", edited, 1)


summary = {"created": "2026-10-10T07:00:00Z",
           "phl:source_updated": "2026-10-09T12:00:00Z"}

due, why = decide("x", WEEKLY, probe("2026-10-15T00:00:00Z"), None, {}, NOW)
check(due and "no version" in why, "a collection with no version is due")

due, why = decide("x", WEEKLY, probe("2026-10-09T12:00:00Z"), summary, {}, NOW)
check(not due and "unchanged" in why, f"an unedited source is skipped: {why}")

due, _ = decide("x", WEEKLY, probe("2026-10-15T00:00:00Z"), summary, {}, NOW)
check(due, "an edit after the current version, past min_days, is due")

recent = dict(summary, **{"created": "2026-10-16T07:00:00Z"})
due, why = decide("x", WEEKLY, probe("2026-10-19T00:00:00Z"), recent, {}, NOW)
check(not due and "2026-10-23" in why, f"min_days holds the version: {why}")

state = {"x": {"source_updated": "2026-10-15T00:00:00Z"}}
due, why = decide("x", WEEKLY, probe("2026-10-15T00:00:00Z"), summary, state, NOW)
check(not due, f"an edit already checked as a no-op is skipped: {why}")

baseline = dict(summary, **{"phl:source_updated": None})
due, _ = decide("x", WEEKLY, probe("2026-10-15T00:00:00Z"), baseline, {}, NOW)
check(due, "a version with no source date is due once min_days pass")


# --- check_styles ---------------------------------------------------------
def parquet(path: Path, **columns) -> str:
    pq.write_table(pa.table(columns), path)
    return str(path)


with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    styles = tmp / "catalog" / "c" / "styles"
    styles.mkdir(parents=True)
    (styles / "default.json").write_text(json.dumps({"layers": [{"paint": {
        "fill-color": ["match", ["get", "code"], [1, 2], "#a", 3, "#b", "#ccc"],
        "fill-opacity": ["step", ["get", "rank"], 0.1, 0.5, 0.9],
    }}]}))
    catalog = tmp / "catalog"

    old = parquet(tmp / "old.parquet", code=[1, 2, 3, 9], rank=[0.1, 0.6, 0.2, 0.7])
    good = parquet(tmp / "good.parquet", code=[1, 2, 3, 9], rank=[0.2, 0.8, 0.3, 0.6])
    check(check_styles.check("c", good, old, catalog) == [],
          "data that keeps every branch and class passes")

    empty_branch = parquet(tmp / "e.parquet", code=[1, 2, 9], rank=[0.2, 0.8, 0.1])
    found = check_styles.check("c", empty_branch, old, catalog)
    check(any("branch 3" in p for p in found), f"an empty branch fails: {found}")

    empty_class = parquet(tmp / "s.parquet", code=[1, 2, 3], rank=[0.1, 0.2, 0.3])
    found = check_styles.check("c", empty_class, old, catalog)
    check(any("holds no row" in p for p in found), f"an empty class fails: {found}")

    new_value = parquet(tmp / "n.parquet", code=[1, 2, 3, 9, 7], rank=[0.1, 0.6, 0.1, 0.6, 0.1])
    found = check_styles.check("c", new_value, old, catalog)
    check(any("new value 7" in p for p in found), f"a new value fails: {found}")
    check(not any("value 9" in p for p in found),
          "a value that fell to the fallback before is left alone")

    gone = parquet(tmp / "g.parquet", rank=[0.1, 0.6])
    found = check_styles.check("c", gone, old, catalog)
    check(any("column is gone" in p for p in found), f"a lost column fails: {found}")


# --- versions in the Collection ---------------------------------------------
BASE = "https://data.example.org/acct/product"

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    catalog = tmp / "catalog"
    (catalog / "c").mkdir(parents=True)
    (catalog / "c" / "collection.json").write_text(json.dumps({
        "type": "Collection", "id": "c", "stac_extensions": [],
        "links": [{"rel": "root", "href": "../catalog.json"},
                  {"rel": "item", "href": "./versions/old.json"}],
        "extent": {"spatial": {"bbox": [[0, 0, 1, 1]]},
                   "temporal": {"interval": [[None, None]]}},
        "assets": {"c": {"href": f"{BASE}/c/c.parquet", "roles": ["data"]}},
        "table:row_count": 0,
    }))
    check(stac.current(catalog, "c") is None, "no version before the first")

    rows = {"2026-10-01": [1, 2, 3], "2026-10-08": [1, 2, 3, 4, 5]}
    sums = {}
    for label, ids in rows.items():
        current = tmp / f"{label}.parquet"
        pq.write_table(pa.table({"id": ids}), current)
        sums[label] = stac.multihash(current)
        stac.add_version(catalog=catalog, collection="c", version=label,
                         parquet=current, pmtiles=None, public_base=BASE,
                         source_updated=f"{label}T01:00:00Z",
                         created=f"{label}T07:00:00Z",
                         extra={"phl:content_hash": f"h-{label}"},
                         update_frequency="weekly", frequency_source="s")

    coll = json.loads((catalog / "c" / "collection.json").read_text())
    now = coll["assets"]["c"]
    old = coll["assets"].get("version-2026-10-01", {})

    check(now["href"] == f"{BASE}/c/c.parquet", "the current asset keeps its URL")
    check(now["version"] == "2026-10-08", "the current asset names its version")
    check(now["file:checksum"] == sums["2026-10-08"], "the current checksum is new")
    check(now["phl:content_hash"] == "h-2026-10-08", "the content hash moves forward")
    check(now["roles"] == ["data"], "the current asset keeps its roles")
    check(old.get("href") == f"{BASE}/c/versions/2026-10-01.parquet",
          "the superseded version points at versions/")
    check(old.get("roles") == ["archive"], "the superseded version is an archive")
    check(old.get("file:checksum") == sums["2026-10-01"],
          "the archive keeps the checksum it had when current")
    check(old.get("table:row_count") == 3, "the archive keeps its row count")
    check(stac.versions(catalog, "c") == ["2026-10-01", "2026-10-08"],
          "versions lists every version, oldest first")
    check(stac.archive_path(tmp / "stage", "c", "2026-10-01")
          == tmp / "stage" / "c" / "versions" / "2026-10-01.parquet",
          "archives stage under versions/")
    check(coll["version"] == "2026-10-08", "the collection names the current version")
    check(coll["table:row_count"] == 5, "the row count is the current version's")
    check(coll["extent"]["temporal"]["interval"]
          == [["2026-10-01T01:00:00Z", "2026-10-08T01:00:00Z"]],
          "the temporal extent spans the versions")
    check(not any(l["rel"] == "item" for l in coll["links"]),
          "no per-version item links remain")
    check(stac.next_version(catalog, "c", "2026-10-08") == "2026-10-08-2",
          "a repeated day gets a suffix, never a reused version")

if errors:
    print("\n".join(f"error  {e}" for e in errors))
    raise SystemExit(1)
print("OK: refresh contract holds")
