# AGENTS.md — City Council Districts (2024)

Guidance for AI agents and LLMs working with this collection.

## Overview

The ten Philadelphia City Council districts as redrawn after the 2020 census. Each elects one council member; the city also seats seven at-large members who represent no district.

Use these boundaries to aggregate any other collection in this catalog by district.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/council_districts_2024/council_districts_2024.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `district` — district number as a **string**, `"1"` through `"10"`. Style expressions and joins must quote it.
- `district_num` — the same value as a small integer, for numeric sorting.
- `shape_leng`, `Shape__Length`, `Shape__Area` — perimeter and area in Web Mercator units.

## Data quality & usage notes

These boundaries took effect for the 2024 election. Analysis of earlier years needs the matching vintage from the publisher, who also releases 1990, 2000, and 2016.

Districts partition the city, so a point falls in exactly one.

Sorting on `district` as a string puts `"10"` between `"1"` and `"2"`. Sort on `district_num` for numeric order.

## Example queries

Aggregate any collection by district. Vacant land, for instance:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c.district, count(*) AS vacant_parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet') v
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, ST_Centroid(v.geometry))
GROUP BY 1 ORDER BY 2 DESC;
```

Affordable housing units delivered per district:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c.district, sum(a.total_units) AS units, count(*) AS projects
FROM read_parquet(getvariable('base') || '/affordable_housing/affordable_housing.parquet') a
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, a.geometry)
GROUP BY 1 ORDER BY 2 DESC;
```

Districts in numeric order:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT district, district_num
FROM read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet')
ORDER BY district_num;
```

## Versions

`council_districts_2024.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher updates it as needed
([source](https://opendataphilly.org/datasets/city-council-districts/)). The catalog checks the source daily and
records a new version at most every 1 day, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- The vacancy collections carry `councildistrict` directly, so aggregating them needs no spatial join.
- Every other collection joins here spatially, centroid against polygon.
