#!/usr/bin/env python3
"""Extract one collection from its ArcGIS service into a GeoParquet file.

The steps repeat the processing the catalog first shipped with, so a refresh
produces the same shape of file:

1. ``portolan extract arcgis --raw --output-crs EPSG:4326``. The published
   files are CRS84, so the refresh writes CRS84 too. The table service goes
   through ``arcgis.fetch_table`` instead (portolan-cli#812).
2. Repair invalid geometries with ``shapely.make_valid`` and its default
   ``linework`` method, as the 2026-08-26 extract did. It repaired 4 in
   dor_parcel, 29 in land_use and 21 in zoning_overlays. The ``structure``
   method gives the same shapes with different vertex order, so every
   unchanged source would hash as changed.
3. ``gpio sort hilbert`` on every spatial collection, so row groups carry
   spatial locality and DuckDB can skip them on a bbox filter.
4. Check the row count against the service's ``returnCountOnly``, read
   before and after the extract. A count that moved during the extract
   means the publisher was mid-edit, and the extract is refused.

``content_hash`` is an order-independent hash over every row. Two extracts
of unchanged source data hash the same even when the service returns rows in
a different order, which is how the refresh skips a no-op version.

    python3 tools/extract.py dor_parcel /tmp/out/dor_parcel.parquet
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from arcgis import fetch_table, layer_url, load_sources, probe  # noqa: E402


EXTRACT_ATTEMPTS = 3
RETRY_PAUSE = 60


@dataclass(frozen=True)
class ExtractResult:
    rows: int
    repaired: int
    null_geometries: int
    content_hash: str


def tool(name: str) -> str:
    """A console script from this interpreter's environment, else from PATH."""
    local = Path(sys.executable).parent / name
    if local.exists():
        return str(local)
    found = shutil.which(name)
    if found is None:
        sys.exit(f"{name} is not installed; see tools/requirements-refresh.txt")
    return found


def run(args: list[str]) -> None:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = (proc.stdout + proc.stderr).strip().splitlines()[-15:]
        raise RuntimeError(f"{args[0]} failed:\n" + "\n".join(tail))


def extract_layer(url: str, workdir: Path) -> Path:
    """Run portolan's raw ArcGIS extract and return the one Parquet it wrote.

    ArcGIS Online sometimes rejects one page of a long extract with "Error
    400 - Cannot perform query" while the city republishes the layer. That
    stopped a 608,085-row dor_parcel extract at offset 54,000. The extract
    is retried from the start, up to EXTRACT_ATTEMPTS times.
    """
    import time

    service = url.rsplit("/", 1)[0]
    for attempt in range(1, EXTRACT_ATTEMPTS + 1):
        out = workdir / f"extract-{attempt}"
        try:
            run([
                tool("portolan"), "extract", "arcgis", "--auto", "--raw",
                "--output-crs", "EPSG:4326", service, str(out),
            ])
            break
        except RuntimeError as exc:
            if attempt == EXTRACT_ATTEMPTS:
                raise
            print(f"  extract attempt {attempt} failed, retrying in "
                  f"{RETRY_PAUSE}s: {str(exc).splitlines()[-1]}", flush=True)
            time.sleep(RETRY_PAUSE)
    files = [p for p in out.rglob("*.parquet") if ".portolan" not in p.parts]
    if len(files) != 1:
        raise RuntimeError(f"expected one parquet from {service}, got {files}")
    return files[0]


def repair_geometries(path: Path) -> tuple[int, int]:
    """Make every invalid geometry valid, in place. Returns (repaired, nulls).

    The bbox covering column is recomputed for repaired rows, because
    make_valid can drop a collapsed part and shrink the extent.
    """
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    import shapely

    table = pq.read_table(path)
    geoms = shapely.from_wkb(table.column("geometry").to_numpy(zero_copy_only=False))
    missing = shapely.is_missing(geoms)
    invalid = ~missing & ~shapely.is_valid(geoms)
    count = int(invalid.sum())
    if count:
        geoms[invalid] = shapely.make_valid(geoms[invalid])
        wkb = shapely.to_wkb(geoms, flavor="iso")
        index = table.schema.get_field_index("geometry")
        table = table.set_column(
            index, table.schema.field(index), pa.array(wkb, pa.binary())
        )
        if "bbox" in table.column_names:
            bounds = shapely.bounds(geoms)
            old = table.column("bbox").combine_chunks()
            names = ["xmin", "ymin", "xmax", "ymax"]
            columns = []
            for i, name in enumerate(names):
                values = old.field(name).to_numpy(zero_copy_only=False).copy()
                values[invalid] = bounds[invalid, i]
                columns.append(pa.array(values, pa.float64()))
            fixed = pa.StructArray.from_arrays(columns, names, mask=pa.array(missing))
            index = table.schema.get_field_index("bbox")
            table = table.set_column(index, table.schema.field(index), fixed)
        pq.write_table(table, path, compression="zstd")
    return count, int(np.asarray(missing).sum())


def hilbert_sort(src: Path, dst: Path) -> None:
    run([tool("gpio"), "sort", "hilbert", str(src), str(dst)])


def content_hash(path: Path) -> str:
    """An order-independent hash of every row, as a decimal string.

    The sum of per-row hashes ignores order and, unlike XOR, does not cancel
    a duplicated row.

    Geometry is hashed after ``ST_Normalize``. Two repairs of one invalid
    polygon give the same shape with a different vertex order: gpio 1.6
    repairs inside the ArcGIS extract with ``ST_MakeValid``, and the
    2026-08-26 extract repaired with shapely. Without normalising, the 29
    repaired land_use rows alone made an unchanged source look changed.
    """
    import duckdb
    import pyarrow.parquet as pq

    con = duckdb.connect()
    source = "read_parquet(?)"
    if "geometry" in pq.ParquetFile(path).schema_arrow.names:
        con.execute("INSTALL spatial; LOAD spatial;")
        source = (f"(SELECT * REPLACE (ST_AsWKB(ST_Normalize(geometry)) "
                  f"AS geometry) FROM {source})")
    value = con.execute(
        "SELECT sum(hash(t)::HUGEINT)::VARCHAR || ':' || count(*) "
        f"FROM {source} t",
        [str(path)],
    ).fetchone()[0]
    return value


def row_count(path: Path) -> int:
    import pyarrow.parquet as pq

    return pq.ParquetFile(path).metadata.num_rows


def extract(collection: str, out: Path, sources: dict | None = None) -> ExtractResult:
    """Extract, repair, sort and check one collection, writing ``out``."""
    sources = sources or load_sources()
    entry = sources["collections"][collection]
    url = layer_url(sources, collection)
    before = probe(sources, collection).count
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"extract-{collection}-") as tmp:
        workdir = Path(tmp)
        if entry["kind"] == "table":
            fetch_table(url, out)
            repaired = nulls = 0
        else:
            raw = extract_layer(url, workdir)
            repaired, nulls = repair_geometries(raw)
            hilbert_sort(raw, out)

    after = probe(sources, collection).count
    rows = row_count(out)
    if not (before == after == rows):
        raise RuntimeError(
            f"{collection}: wrote {rows} rows, service reported {before} "
            f"before and {after} after; the source changed mid-extract"
        )
    return ExtractResult(rows, repaired, nulls, content_hash(out))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("collection")
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    result = extract(args.collection, args.out)
    print(f"{args.collection}: {result.rows} rows, {result.repaired} repaired, "
          f"{result.null_geometries} null geometries, hash {result.content_hash}")
