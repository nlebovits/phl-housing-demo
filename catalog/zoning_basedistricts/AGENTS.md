# AGENTS.md — Zoning Base Districts

Guidance for AI agents and LLMs working with this collection.

## Overview

Boundaries of Philadelphia's zoning base districts under the code enacted in December 2011 and effective 22 August 2012.

A base district sets what may be built on a parcel and how it may be used. Read it with [zoning_overlays](../zoning_overlays), which layer extra rules on top.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/zoning_basedistricts/zoning_basedistricts.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `long_code` — district code with dashes, e.g. `RSA-5`. Joins to `zoning_descriptions.new_code`.
- `code` — the same code without dashes, e.g. `RSA5`. This is what the styles key on.
- `zoninggroup` — four broad families: Residential/Multi-Family/Residential Mixed-Use, Commercial/Commercial Mixed-Use, Industrial/Industrial Mixed-Use, and Special Purpose. Residential polygons are the most numerous and Special Purpose the fewest.
- `pending`, `pendingbill`, `pendingbillurl` — legislation that would change this district.
- `sunset_date`, `sunsetbillnum`, `sunsetbilllink` — when a district expires and the bill that set that date.
- `citycor` — flag whose meaning the publisher does not document.

Every distinct code present in the data resolves through [zoning_descriptions](../zoning_descriptions). The most common are RSA-5, CMX-2, RM-1, and CMX-1. The first example query below counts polygons per code.

## Data quality & usage notes

This is the current vintage. The publisher also releases 2015, 2016, 2020, 2021, and 2025 layers, which this catalog does not carry.

`pendingbillurl` and `sunsetbilllink` point at city legislative records that move independently of this dataset, so some links go stale.

Polygons partition the city, so a point falls in exactly one base district.

## Example queries

Zoning codes with readable names. Every row matches:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.long_code, d.code_description, count(*) AS polygons
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
JOIN read_parquet(getvariable('base') || '/zoning_descriptions/zoning_descriptions.parquet') d
  ON z.long_code = d.new_code
GROUP BY 1, 2 ORDER BY 3 DESC;
```

Zoning mix within one council district:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.zoninggroup, count(*) AS polygons
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, ST_Centroid(z.geometry))
WHERE c.district = '5'
GROUP BY 1 ORDER BY 2 DESC;
```

Districts with pending legislation:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT long_code, pendingbill, pendingbillurl
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet')
WHERE pendingbill IS NOT NULL
LIMIT 20;
```

## Versions

`zoning_basedistricts.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states no update cadence
([source](https://opendataphilly.org/datasets/zoning-base-districts/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [zoning_descriptions](../zoning_descriptions) — the decoder for `long_code`.
- [zoning_overlays](../zoning_overlays) — additional rules stacked on top.
- [land_use](../land_use) — actual use, against permitted use here.
