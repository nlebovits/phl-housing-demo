# phl-housing-demo

Metadata for the [Philadelphia Housing and Land
Use](https://source.coop/nlebovits/phl-housing-demo) catalog on Source
Cooperative. Ten collections describing property, zoning, vacancy, and
affordable housing in Philadelphia, mirrored from the City of Philadelphia's
ArcGIS services via [OpenDataPhilly](https://opendataphilly.org/).

This repository holds the catalog's STAC metadata, map styles, thumbnails,
documentation, and the refresh pipeline. The data lives in the bucket.

| Collection | Geometry | What it answers |
|---|---|---|
| Property parcels | Polygon | Where are the property boundaries? |
| Land use | Polygon | What is happening on this land? |
| Building footprints | Polygon | Where are the buildings, and how tall? |
| Zoning base districts | Polygon | What does the code permit here? |
| Vacant indicators — land | Polygon | Which lots look empty? |
| Vacant indicators — buildings | Polygon | Which buildings look empty? |
| Affordable housing production | Point | Where has the city funded housing? |
| Zoning overlays | Polygon | What extra rules apply here? |
| Zoning code descriptions | None | What does this zoning code mean? |
| City council districts (2024) | Polygon | Who represents this area? |

## Reading the data

Every collection is GeoParquet in CRS84 (longitude, latitude), with PMTiles
alongside for rendering. Each one has a fixed URL for its current data:

```
https://data.source.coop/nlebovits/phl-housing-demo/<collection>/<collection>.parquet
```

Read one over HTTP with DuckDB:

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SET VARIABLE base =
  'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.long_code, d.code_description, count(*) AS polygons
FROM read_parquet(getvariable('base')
     || '/zoning_basedistricts/zoning_basedistricts.parquet') z
JOIN read_parquet(getvariable('base')
     || '/zoning_descriptions/zoning_descriptions.parquet') d
  ON z.long_code = d.new_code
GROUP BY 1, 2 ORDER BY 3 DESC;
```

Coordinates are degrees, so `ST_Area(geometry)` returns square degrees.
Reproject to EPSG:2272 before you measure.

[catalog/AGENTS.md](catalog/AGENTS.md) covers join keys, worked queries, and
the data quirks that cause most wrong answers. Each collection has its own
agent guide beside its `collection.json`.

## Versions

A scheduled job checks every source daily. When the city changes a
collection's rows, the job records a new version:

```
<collection>/<collection>.parquet           the current version
<collection>/versions/<version>.parquet     each earlier version, never changed
<collection>/collection.json                every version, with its dates and checksum
```

The version is the date of the extract. The first version of every collection
is `2026-08-26`. Read an earlier version like the current one:

```sql
SELECT count(*)
FROM read_parquet(getvariable('base')
     || '/dor_parcel/versions/2026-08-26.parquet');
```

The current row count of each collection is `table:row_count` in its
`collection.json`. The documentation quotes no counts, because they change
with every version.

[docs/refresh.md](docs/refresh.md) explains how the job decides what to
refresh, how often each collection can change, and how to run it by hand.

## Contributing

Metadata errors are worth fixing, and a pull request is the way. Wrong license
text, a column description that misreads the data, a broken link, or a style
whose legend does not match what renders: all of these are in scope.

```bash
git clone https://github.com/nlebovits/phl-housing-demo
cd phl-housing-demo

python3 -m venv .venv
.venv/bin/pip install 'rashid>=0.1.5,<0.2.0' stac-check duckdb pyarrow

# make the edit, then
.venv/bin/python3 tests/run_all.py
```

CI runs the same gates on every pull request:

- `rashid` for Portolan conformance and `stac-check` for STAC hygiene
- link resolution
- the refresh pipeline's offline contract
- a check that the docs quote no counts or percentages from the data
- every SQL block in the documentation, run against the published bucket

A query in the docs that no longer runs is a bug, so CI fails when one breaks.

Do not run `portolan push` on this catalog. The refresh workflow is the only
tool that writes data to the bucket. See [AGENTS.md](AGENTS.md).

## License

The data is published by the City of Philadelphia under the City of
Philadelphia License, which reserves rights rather than granting them. The
terms state the city "reserves all rights in the database and any data
contained therein" and that use "does not constitute a transfer of, nor does
the end user receive, any title or interest in the database". Data is offered
"as is" and without warranty of any kind.

No SPDX identifier applies, and no explicit redistribution grant accompanies
the datasets. Read the [city's
terms](https://metadata.phila.gov/#help/help-faqs/what-are-the-terms-of-use/)
before redistributing or using this data commercially.

The tooling in this repository is MIT licensed. See [LICENSE](LICENSE).
