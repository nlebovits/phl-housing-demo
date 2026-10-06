# AGENTS.md — Zoning Overlays

Guidance for AI agents and LLMs working with this collection.

## Overview

Boundaries of Philadelphia's zoning overlay districts, enacted 15 December 2011 and effective 22 August 2012.

An overlay adds rules on top of the base district beneath it. A single parcel can sit under several overlays at once, so these polygons deliberately intersect.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/zoning_overlays/zoning_overlays.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `overlay_name` — the overlay's full name.
- `overlay_symbol` — its short symbol, e.g. `/CTR`, `/NCA`, `/NCO`, `/TOC`. Some polygons carry the literal string `[N/A]`.
- `type` — three values: Overlay District, Supplemental Control, and Wissahickon Watershed Impervious Coverage Restriction. The "Overlays by type" query below counts each.
- `code_section`, `code_section_link` — the section of the zoning code that created the overlay, and a link to its text.
- `pending`, `pendingbill`, `pendingbillurl`, `sunset_date`, `sunsetbillnum`, `sunsetbilllink` — pending and expiring legislation, as in [zoning_basedistricts](../zoning_basedistricts).

## Data quality & usage notes

**Overlays intersect by design.** They are not a partition of the city. Summing `Shape__Area` across overlays double-counts any ground covered by more than one. Dissolve first if you need total covered area.

Invalid geometries were repaired during the 2026-08-26 extraction.

Some rows carry `[N/A]` as their symbol, a literal string rather than a null. Filter with `overlay_symbol <> '[N/A]'`, not `IS NOT NULL`.

## Example queries

Every rule applying at one point, base district and overlays together:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

WITH pt AS (SELECT ST_Point(-8367000, 4859000) AS g)
SELECT 'base' AS kind, z.long_code AS name
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z, pt
WHERE ST_Intersects(z.geometry, pt.g)
UNION ALL
SELECT 'overlay', o.overlay_name
FROM read_parquet(getvariable('base') || '/zoning_overlays/zoning_overlays.parquet') o, pt
WHERE ST_Intersects(o.geometry, pt.g);
```

Overlays by type:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT type, count(*) AS polygons
FROM read_parquet(getvariable('base') || '/zoning_overlays/zoning_overlays.parquet')
GROUP BY 1 ORDER BY 2 DESC;
```

Named overlays with their code sections:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT overlay_symbol, overlay_name, code_section
FROM read_parquet(getvariable('base') || '/zoning_overlays/zoning_overlays.parquet')
WHERE overlay_symbol <> '[N/A]'
ORDER BY overlay_symbol;
```

## Versions

`zoning_overlays.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states no update cadence
([source](https://opendataphilly.org/datasets/zoning-overlays/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [zoning_basedistricts](../zoning_basedistricts) — the base rules an overlay modifies.
- [zoning_descriptions](../zoning_descriptions) — decodes base district codes, not overlay symbols.
