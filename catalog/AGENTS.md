# AGENTS.md — Philadelphia Housing and Land Use

Guidance for AI agents and LLMs working with this catalog.

## Overview

Ten collections describing property, zoning, vacancy, and affordable housing
in Philadelphia, mirrored from the City of Philadelphia's ArcGIS services via
[OpenDataPhilly](https://opendataphilly.org/). Together they answer questions
about what exists on a parcel, what the code permits there, whether the city
believes it is empty, and what publicly funded housing has been built.

Every collection is GeoParquet in EPSG:3857 (Web Mercator) with a PMTiles
rendering alongside it. One collection, `zoning_descriptions`, is a lookup
table with no geometry.

## Collections

| Collection | Rows | Geometry | What it answers |
|---|---|---|---|
| `dor_parcel` | 607,957 | Polygon | Where are the property boundaries? |
| `land_use` | 559,077 | Polygon | What is happening on this land? |
| `li_building_footprints` | 546,083 | Polygon | Where are the buildings, and how tall? |
| `zoning_basedistricts` | 29,205 | Polygon | What does the code permit here? |
| `vacant_indicators_land` | 28,737 | Polygon | Which lots look empty? |
| `vacant_indicators_bldg` | 9,041 | Polygon | Which buildings look empty? |
| `affordable_housing` | 501 | Point | Where has DHCD funded housing? |
| `zoning_overlays` | 195 | Polygon | What extra rules apply here? |
| `zoning_descriptions` | 39 | None | What does this zoning code mean? |
| `council_districts_2024` | 10 | Polygon | Who represents this area? |

Each collection has its own `AGENTS.md` with schema notes and worked queries.

## Data access patterns

Read any collection directly over HTTP with DuckDB. Use `data.source.coop` for
byte fetches; `source.coop` serves the human-readable pages.

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT count(*)
FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/'
  || 'zoning_basedistricts/zoning_basedistricts.parquet'
);
```

Working locally is faster for repeated analysis:

```bash
aws s3 sync \
  s3://us-west-2.opendata.source.coop/nlebovits/phl-housing-demo/ \
  ./phl-housing-demo --no-sign-request
```

### Geometry

DuckDB's spatial extension reads the `geometry` column natively. Do not wrap it
in `ST_GeomFromWKB`, which fails with a binder error because the column is
already a `GEOMETRY`:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

-- correct
SELECT count(*) FROM read_parquet(getvariable('base') || '/land_use/land_use.parquet')
WHERE ST_Area(geometry) > 1000;
```

Coordinates are EPSG:3857 metres, so `ST_Area` returns square metres distorted
by latitude. At Philadelphia's latitude the scale factor is about 1.3, meaning
Web Mercator areas run roughly 1.7x larger than ground truth. Reproject to
EPSG:2272 (Pennsylvania South, US survey feet) for measurements that matter.

### Joining collections

Two joins are attested and verified against the published data.

**Zoning codes to their meanings.** 29,205 of 29,205 rows match:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.long_code, d.code_description, count(*) AS polygons
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
JOIN read_parquet(getvariable('base') || '/zoning_descriptions/zoning_descriptions.parquet') d
  ON z.long_code = d.new_code
GROUP BY 1, 2 ORDER BY 3 DESC;
```

**Vacancy to parcels, by address.** 27,688 of 28,737 rows match (96%):

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT v.address, v.land_rank, p.basereg
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet') v
JOIN read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet') p
  ON upper(trim(v.address)) = upper(trim(p.addr_std));
```

Identifier columns do **not** join across collections, which is worth stating
plainly because their names suggest otherwise. `opa_id` in the vacancy
collections is an Office of Property Assessment account number and matches
nothing in `dor_parcel.pin`, a Department of Records parcel identifier: the
join returns zero rows. `parcel_id_num` in `li_building_footprints` carries
`parcel_id_source = 'PWD'`, a Water Department identifier, and likewise does
not match. Join on normalized address, or join spatially.

**Spatially**, when no shared key exists. Intersect a centroid against the
containing polygon rather than polygon-to-polygon, which is both faster and
free of edge-touching false positives:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c.district, count(*) AS vacant_parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet') v
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, ST_Centroid(v.geometry))
GROUP BY 1 ORDER BY 2 DESC;
```

This returns a real result: District 5 holds 9,178 vacant parcels against 268
in District 10.

The vacancy collections also carry `councildistrict` and `zoningbasedistrict`
as plain columns, so aggregating them by district needs no spatial join at all.

## Cross-collection questions

**Where is vacant land zoned for housing?** 39,411 vacant parcels sit on
residentially zoned land:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.zoninggroup, count(*) AS vacant_parcels
FROM read_parquet(getvariable('base') || '/land_use/land_use.parquet') l
JOIN read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
  ON ST_Intersects(z.geometry, ST_Centroid(l.geometry))
WHERE l.c_dig1 = 9
GROUP BY 1 ORDER BY 2 DESC;
```

## Traps worth knowing

Four quirks account for most wrong answers against this catalog.

**Land use descriptions are mostly unusable.** 515,369 of 559,077 rows (92%)
store a bare digit in `c_dig1desc` rather than a label. Read the numeric code
columns and map them yourself; see `land_use/AGENTS.md`.

**Vacancy ranks are repeating decimals.** The stored values are `0.5`,
`0.6666666700000001`, `0.8333333300000001`, and `1.0`. Comparing with `= 0.67`
silently matches nothing. Use ranges.

**Affordable housing types are semicolon-joined.** `project_type` holds values
like `Rental;Special Needs;Mixed Use`. Grouping on the raw column treats each
combination as its own category, undercounting rental projects at 242 instead
of 262. Split on `;` first.

**Null geometry exists.** 37 parcels and 25 affordable housing projects have
attributes but no geometry, and they sort to the end of the file.

## License

Data is published by the City of Philadelphia under the City of Philadelphia
License, which reserves rights rather than granting them. The terms state the
city "reserves all rights in the database and any data contained therein" and
that use "does not constitute a transfer of, nor does the end user receive, any
title or interest in the database". Data is offered "as is" and without
warranty of any kind.

No SPDX identifier applies, and no explicit redistribution grant accompanies
the datasets. Read the
[city's terms](https://metadata.phila.gov/#help/help-faqs/what-are-the-terms-of-use/)
before redistributing or using this data commercially.
