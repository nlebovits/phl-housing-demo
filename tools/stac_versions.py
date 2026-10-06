#!/usr/bin/env python3
"""Record each extract as a version, in the Collection itself.

One copy of every extract exists in the bucket:

- ``<coll>/<coll>.parquet`` is the current version. Its URL never changes.
- ``<coll>/versions/<version>.parquet`` holds each earlier version. A refresh
  archives the outgoing current file there before it replaces it, and the
  file never changes after that.

``collection.json`` describes all of them. The asset named after the
collection is the current version. Each earlier version is an asset named
``version-<version>`` with the role ``archive``. Every version asset carries:

- ``version``: the UTC date of the extract (``2026-10-06``, or
  ``2026-10-06-2`` for a forced second run that day)
- ``created``: when this catalog extracted the rows
- ``phl:source_updated``: the publisher's ``dataLastEditDate`` for the rows,
  or null for the 2026-08-26 extract, which predates edit tracking
- ``table:row_count``, ``file:size``, ``file:checksum``
- ``phl:content_hash``: an order-independent hash of the rows, which the
  refresh uses to skip an extract that changed nothing

The Collection's ``version`` names the current version (STAC version
extension, PORTO-CORE-008).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

VERSION_EXT = "https://stac-extensions.github.io/version/v1.2.0/schema.json"
PARQUET = "application/vnd.apache.parquet"
ARCHIVE_PREFIX = "version-"
VERSION_FIELDS = ("version", "created", "phl:source_updated", "table:row_count",
                  "phl:content_hash", "phl:repaired_geometries",
                  "phl:null_geometries", "file:size", "file:checksum")


def multihash(path: Path) -> str:
    """The sha2-256 multihash the file extension uses for file:checksum."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return "1220" + digest.hexdigest()


def file_fields(path: Path) -> dict:
    return {"file:size": path.stat().st_size, "file:checksum": multihash(path)}


def parquet_facts(path: Path) -> dict:
    """Row count, columns and (for GeoParquet) bbox."""
    import pyarrow.parquet as pq

    handle = pq.ParquetFile(path)
    schema = handle.schema_arrow
    facts = {
        "rows": handle.metadata.num_rows,
        "columns": [{"name": f.name, "type": str(f.type)} for f in schema],
        "bbox": None,
    }
    geo = (schema.metadata or {}).get(b"geo")
    if geo:
        column = json.loads(geo)["columns"]["geometry"]
        facts["bbox"] = [round(v, 10) for v in column.get("bbox", [])] or None
    return facts


def current_href(public_base: str, collection: str) -> str:
    return f"{public_base}/{collection}/{collection}.parquet"


def archive_href(public_base: str, collection: str, version: str) -> str:
    return f"{public_base}/{collection}/versions/{version}.parquet"


def archive_path(data_dir: Path, collection: str, version: str) -> Path:
    """Where the staging directory holds an archived version for upload."""
    return data_dir / collection / "versions" / f"{version}.parquet"


def load(catalog: Path, collection: str) -> dict:
    return json.loads((catalog / collection / "collection.json").read_text())


def current(catalog: Path, collection: str) -> dict | None:
    """The current version asset, or None before the first version."""
    asset = load(catalog, collection)["assets"].get(collection, {})
    return asset if "version" in asset else None


def versions(catalog: Path, collection: str) -> list[str]:
    """Every version, oldest first. Versions sort as dates."""
    assets = load(catalog, collection)["assets"]
    found = [a["version"] for key, a in assets.items()
             if key.startswith(ARCHIVE_PREFIX) or (key == collection and "version" in a)]
    return sorted(found)


def next_version(catalog: Path, collection: str, day: str) -> str:
    """``day``, or ``day-2``, ``day-3``... when a forced rerun repeats a day."""
    taken = set(versions(catalog, collection))
    label, n = day, 1
    while label in taken:
        n += 1
        label = f"{day}-{n}"
    return label


def add_version(
    *,
    catalog: Path,
    collection: str,
    version: str,
    parquet: Path,
    pmtiles: Path | None,
    public_base: str,
    source_updated: str | None,
    created: str,
    extra: dict,
    update_frequency: str,
    frequency_source: str,
) -> None:
    """Make ``parquet`` the current version and archive the one before.

    The outgoing current asset becomes ``version-<its version>`` at
    ``versions/<its version>.parquet``, with its size and checksum unchanged,
    so a reader can prove the archive holds the bytes that were current.
    """
    path = catalog / collection / "collection.json"
    doc = json.loads(path.read_text())
    assets = doc["assets"]
    facts = parquet_facts(parquet)

    old = assets[collection]
    if "version" in old:
        assets[f"{ARCHIVE_PREFIX}{old['version']}"] = {
            "href": archive_href(public_base, collection, old["version"]),
            "type": PARQUET,
            "title": f"{collection} as extracted on {old['version']}",
            "roles": ["archive"],
            **{k: old[k] for k in VERSION_FIELDS if k in old},
        }

    for key in VERSION_FIELDS:
        old.pop(key, None)
    old.update({
        "href": current_href(public_base, collection),
        "version": version,
        "created": created,
        "phl:source_updated": source_updated,
        "table:row_count": facts["rows"],
        **extra,
        **file_fields(parquet),
    })
    if pmtiles is not None and f"{collection}-tiles" in assets:
        assets[f"{collection}-tiles"].update(file_fields(pmtiles))

    if VERSION_EXT not in doc["stac_extensions"]:
        doc["stac_extensions"].append(VERSION_EXT)
    doc["version"] = version
    doc["updated"] = created
    doc["phl:source_updated"] = source_updated
    doc["phl:update_frequency"] = update_frequency
    doc["phl:update_frequency_source"] = frequency_source
    doc["table:row_count"] = facts["rows"]
    doc["table:columns"] = facts["columns"]
    if "geoparquet:feature_count" in doc:
        doc["geoparquet:feature_count"] = facts["rows"]
    if facts["bbox"]:
        doc["extent"]["spatial"]["bbox"] = [facts["bbox"]]
    times = [a.get("phl:source_updated") or a["created"] for key, a in assets.items()
             if key.startswith(ARCHIVE_PREFIX) or key == collection]
    doc["extent"]["temporal"]["interval"] = [[min(times), max(times)]]
    doc["links"] = [l for l in doc["links"]
                    if l["rel"] not in ("item", "latest-version")]
    write_json(path, doc)


def write_json(path: Path, doc: dict) -> None:
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
