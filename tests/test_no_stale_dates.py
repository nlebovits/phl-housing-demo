#!/usr/bin/env python3
"""The docs name no date that the next refresh makes wrong.

Every refresh can replace the current file of a collection. A sentence such
as "Extracted 2026-08-26 from the DOR_Parcel FeatureServer" is then wrong,
and nothing rewrites it. The date of each version lives in collection.json,
which the refresh writes. The docs point there.

This gate reads the documents in tests/doc_corpus.py and fails on:

- an ISO date (2026-08-26) in a sentence
- a year after "extracted", "written", "retrieved", "downloaded", "fetched",
  or "as of" in the same sentence

A sentence that names the first version keeps its date, because the first
version never changes. A ``versions/<date>.parquet`` path is an archive,
which never changes either. Dates the publisher gives in words, such as
"22 August 2012", are not ISO dates and pass.

It also fails when the root catalog.json ``updated`` differs from the newest
Collection ``updated``. tools/refresh.py keeps the two equal.

Run: python3 tests/test_no_stale_dates.py
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

from doc_corpus import CATALOG, ROOT, documents  # noqa: E402
from stac_versions import newest_update  # noqa: E402

ISO_DATE = re.compile(r"(?<![\w/-])(?:19|20)\d\d-\d\d-\d\d(?![\w-])")
ARCHIVE = re.compile(r"versions/(?:19|20)\d\d-\d\d-\d\d(?:-\d+)?\.parquet")
DATED_EXTRACT = re.compile(
    r"\b(?:extracted|written|retrieved|downloaded|fetched|as of)\b"
    r"[^.\n]{0,60}?\b(?:19|20)\d\d\b",
    re.I,
)
FIRST_VERSION = re.compile(r"\bfirst (?:version|one|extract)\b", re.I)
# A sentence ends at . ! or ?, at a blank line, or before a list item, a
# heading or a table row. A single newline inside a paragraph is a wrap.
SENTENCE = re.compile(r"(?<=[.!?])\s+|\n\s*\n|\n(?=\s*(?:[-*#|]|\d+\.\s))")

errors = []
docs = documents()
for path, prose in docs:
    offset = 0
    for sentence in SENTENCE.split(prose):
        line = prose[:prose.find(sentence, offset)].count("\n") + 1
        offset = prose.find(sentence, offset) + len(sentence)
        if FIRST_VERSION.search(sentence):
            continue
        text = ARCHIVE.sub("", sentence)
        found = ISO_DATE.search(text) or DATED_EXTRACT.search(text)
        if found:
            errors.append(f"{path.relative_to(ROOT)}:{line}: {found.group(0)!r} "
                          f"in {sentence.strip()[:100]!r}")

root = json.loads((CATALOG / "catalog.json").read_text())
newest = newest_update(CATALOG)
if root.get("updated") != newest:
    errors.append(f"catalog/catalog.json: updated is {root.get('updated')}, "
                  f"but the newest Collection was updated {newest}. "
                  "Run: python3 -c 'import sys; sys.path.insert(0, \"tools\"); "
                  "import stac_versions as s; from pathlib import Path; "
                  "s.stamp_catalog(Path(\"catalog\"))'")

if errors:
    print("\n".join(f"error  dated claim about the current data: {e}" for e in errors))
    print("       Point to the version list in collection.json instead, or name "
          "the first version.")
    raise SystemExit(1)
print(f"OK: no stale dates in {len(docs)} document(s); catalog.json updated "
      f"is {newest}")
