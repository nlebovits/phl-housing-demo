#!/usr/bin/env python3
"""Read the state of the city's ArcGIS services, and fetch the one table.

Every collection mirrors layer 0 of one FeatureServer, listed in
``tools/sources.json``. Two numbers decide whether a refresh is needed:

- ``editingInfo.dataLastEditDate``: when the publisher last changed rows.
  Schema edits move ``lastEditDate`` but not this value, so a schema-only
  edit does not trigger a re-extract.
- ``returnCountOnly``: the row count the extract must reproduce.

``zoning_descriptions`` is a table, not a layer. ``portolan extract arcgis``
reports "0/0 layers" for it (portolan-cli#812), so ``fetch_table`` pages the
query endpoint here instead.

Standard library only, apart from pyarrow in ``fetch_table``.
"""
from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SOURCES = Path(__file__).resolve().parent / "sources.json"

# ArcGIS Online throttles bursts. Three tries with a growing pause cover the
# transient 5xx and timeout responses seen from services.arcgis.com.
RETRIES = 3
TIMEOUT = 60


@dataclass(frozen=True)
class SourceState:
    """What the service reports right now for one collection."""

    collection: str
    layer_url: str
    data_last_edit: str
    count: int


def load_sources(path: Path = SOURCES) -> dict:
    return json.loads(path.read_text())


def layer_url(sources: dict, collection: str) -> str:
    entry = sources["collections"][collection]
    return f"{sources['org_url']}/{entry['service']}/FeatureServer/0"


def get_json(url: str, params: dict[str, str] | None = None) -> dict:
    """GET a JSON document, retrying transient failures.

    ArcGIS reports most errors with HTTP 200 and an ``error`` member, so that
    member is raised as an error too.
    """
    query = urllib.parse.urlencode({**(params or {}), "f": "json"})
    full = f"{url}?{query}"
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(full, timeout=TIMEOUT) as response:
                body = json.load(response)
            if "error" in body:
                raise RuntimeError(f"{url}: {body['error']}")
            return body
        except (OSError, json.JSONDecodeError, RuntimeError):
            if attempt == RETRIES:
                raise
            time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def iso_from_ms(ms: int) -> str:
    """An ArcGIS epoch-millisecond value as an ISO 8601 UTC string."""
    moment = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def probe(sources: dict, collection: str) -> SourceState:
    """The service's data edit time and row count for one collection."""
    url = layer_url(sources, collection)
    info = get_json(url)
    editing = info.get("editingInfo") or {}
    edited = editing.get("dataLastEditDate") or editing.get("lastEditDate")
    if edited is None:
        raise RuntimeError(f"{url} reports no editingInfo; cannot detect edits")
    count = get_json(f"{url}/query", {"where": "1=1", "returnCountOnly": "true"})
    return SourceState(collection, url, iso_from_ms(edited), int(count["count"]))


# Esri field types and the Arrow types the published table already uses.
# zoning_descriptions shipped objectid as int32, so OID maps to int32.
ESRI_TO_ARROW = {
    "esriFieldTypeOID": "int32",
    "esriFieldTypeInteger": "int32",
    "esriFieldTypeSmallInteger": "int16",
    "esriFieldTypeDouble": "float64",
    "esriFieldTypeSingle": "float32",
    "esriFieldTypeString": "string",
    "esriFieldTypeGUID": "string",
    "esriFieldTypeGlobalID": "string",
    "esriFieldTypeDate": "timestamp_ms",
}


def fetch_table(url: str, out: Path) -> int:
    """Write every row of a non-spatial ArcGIS table to GeoParquet-free Parquet.

    Pages by objectid order with ``resultOffset`` until the service stops
    reporting ``exceededTransferLimit``. Returns the row count written.
    """
    import pyarrow as pa
    import pyarrow.parquet as pq

    info = get_json(url)
    page = int(info.get("maxRecordCount") or 1000)
    fields = info["fields"]
    oid = next(f["name"] for f in fields if f["type"] == "esriFieldTypeOID")

    rows: list[dict] = []
    offset = 0
    while True:
        body = get_json(f"{url}/query", {
            "where": "1=1",
            "outFields": "*",
            "orderByFields": oid,
            "resultOffset": str(offset),
            "resultRecordCount": str(page),
        })
        features = body.get("features", [])
        rows.extend(f["attributes"] for f in features)
        offset += len(features)
        if not features or not body.get("exceededTransferLimit"):
            break

    columns = {}
    for field in fields:
        kind = ESRI_TO_ARROW.get(field["type"])
        if kind is None:
            raise RuntimeError(f"{url}: unmapped field type {field['type']}")
        values = [row.get(field["name"]) for row in rows]
        if kind == "timestamp_ms":
            columns[field["name"]] = pa.array(values, pa.timestamp("ms", "UTC"))
        else:
            columns[field["name"]] = pa.array(values, getattr(pa, kind)())
    out.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.table(columns), out, compression="zstd")
    return len(rows)


if __name__ == "__main__":
    import sys

    data = load_sources()
    names = sys.argv[1:] or sorted(data["collections"])
    for name in names:
        state = probe(data, name)
        print(f"{name:24} {state.data_last_edit}  {state.count:>8} rows")
