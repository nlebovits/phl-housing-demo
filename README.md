# phl-housing-demo

Metadata for the [Philadelphia Housing and Land
Use](https://source.coop/nlebovits/phl-housing-demo) catalog on Source
Cooperative. Ten collections describing property, zoning, vacancy, and
affordable housing in Philadelphia, mirrored from the City of Philadelphia's
ArcGIS services via [OpenDataPhilly](https://opendataphilly.org/).

The catalog holds 1,780,845 features. This repository holds its STAC metadata,
map styles, thumbnails, and documentation. The data lives in the bucket.

| Collection | Rows | Geometry |
|---|---|---|
| Property parcels | 607,957 | Polygon |
| Land use | 559,077 | Polygon |
| Building footprints | 546,083 | Polygon |
| Zoning base districts | 29,205 | Polygon |
| Vacant indicators — land | 28,737 | Polygon |
| Vacant indicators — buildings | 9,041 | Polygon |
| Affordable housing production | 501 | Point |
| Zoning overlays | 195 | Polygon |
| Zoning code descriptions | 39 | None |
| City council districts (2024) | 10 | Polygon |

## Reading the data

Every collection is GeoParquet in EPSG:3857, with PMTiles alongside for
rendering. Read one over HTTP with DuckDB:

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

[catalog/AGENTS.md](catalog/AGENTS.md) covers join keys, worked queries, and
the four data quirks that cause most wrong answers. Each collection has its own
agent guide beside its `collection.json`.

## Contributing

Metadata errors are worth fixing, and a pull request is the way. Wrong license
text, a column description that misreads the data, a broken link, or a style
whose legend does not match what renders: all of these are in scope.

```bash
git clone https://github.com/nlebovits/phl-housing-demo
cd phl-housing-demo

python3 -m venv .venv
.venv/bin/pip install 'rashid>=0.1.5,<0.2.0' stac-check

# make the edit, then
.venv/bin/python3 tests/run_all.py
```

CI runs the same gates on every pull request: `rashid` for Portolan
conformance, `stac-check` for STAC hygiene, link resolution, and every SQL
block in the documentation executed against the published bucket.

That last gate is the unusual one. A query in the docs that no longer runs is a
bug, so CI fails when one breaks.

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
