# AGENTS.md — Land Use

Guidance for AI agents and LLMs working with this collection.

## Overview

Land use assigned to each parcel by the City Planning Commission. 559,077 polygons recording the activity on the ground, which is distinct from what zoning permits.

Use this to ask what a place *is*. Use [zoning_basedistricts](../zoning_basedistricts) to ask what it *may become*.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/land_use/land_use.parquet'
) LIMIT 5;
```

Coordinates are EPSG:3857 (Web Mercator) metres. DuckDB reads `geometry`
natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

The classification is hierarchical, one digit deeper at each level:

- `c_dig1` — major class, 1 through 9.
- `c_dig2` — sub-class, two digits, e.g. `11` under major class 1.
- `c_dig3` — finest class, three digits.

Major classes and their counts:

| Code | Meaning | Parcels |
|---|---|---|
| 1 | Residential | 471,793 |
| 2 | Commercial | 22,607 |
| 3 | Industrial | 4,699 |
| 4 | Civic / Institution | 3,925 |
| 5 | Transportation | 4,684 |
| 6 | Culture / Recreation | 835 |
| 7 | Park / Open Space | 1,788 |
| 8 | Water | 282 |
| 9 | Vacant | 48,464 |

Sub-classes seen in the data: 11 Residential Low Density, 12 Residential Medium Density, 13 Residential High Density, 21 Commercial Consumer, 22 Commercial Business/Professional, 23 Commercial Mixed Residential, 31 Industrial, 41 Civic/Institution, 51 Transportation, 52 Greened ROW, 61 Culture/Amusement, 62 Active Recreation, 71 Park/Open Space, 72 Cemetery, 81 Water, 91 Vacant, 92 Other/Unknown.

- `year` — survey year. Every row is 2023 or 2025.
- `vacbldg` — `V` on 175 rows, null on 558,902. Effectively unpopulated; use the [vacancy collections](../vacant_indicators_bldg) instead.

## Data quality & usage notes

**The description columns are mostly unusable.** 515,369 of 559,077 rows (92%) store a bare digit in `c_dig1desc` rather than a label, so a query returns `"1"` where you expect `"1 Residential"`. `c_dig2desc` and `c_dig3desc` behave the same way.

The numeric code columns are clean and fully populated. Read those and map them yourself, as the first query below does.

29 invalid geometries were repaired during extraction. The file is Hilbert-sorted, so row groups carry spatial locality and a bbox filter can skip most of the file.

## Example queries

Label the major classes without touching the broken description columns:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT CASE c_dig1
         WHEN 1 THEN 'Residential'   WHEN 2 THEN 'Commercial'
         WHEN 3 THEN 'Industrial'    WHEN 4 THEN 'Civic/Institution'
         WHEN 5 THEN 'Transportation' WHEN 6 THEN 'Culture/Recreation'
         WHEN 7 THEN 'Park/Open Space' WHEN 8 THEN 'Water'
         WHEN 9 THEN 'Vacant'
       END AS land_use,
       count(*) AS parcels
FROM read_parquet(getvariable('base') || '/land_use/land_use.parquet')
GROUP BY 1 ORDER BY 2 DESC;
```

Where is vacant land zoned for housing? Returns 39,411 parcels on residential land:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT z.zoninggroup, count(*) AS vacant_parcels
FROM read_parquet(getvariable('base') || '/land_use/land_use.parquet') l
JOIN read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
  ON ST_Intersects(z.geometry, ST_Centroid(l.geometry))
WHERE l.c_dig1 = 9
GROUP BY 1 ORDER BY 2 DESC;
```

Residential density mix:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c_dig2, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/land_use/land_use.parquet')
WHERE c_dig2 IN (11, 12, 13)
GROUP BY 1 ORDER BY 1;
```

## Related collections

- [zoning_basedistricts](../zoning_basedistricts) — permitted use, against actual use here.
- [dor_parcel](../dor_parcel) — the underlying property boundaries.
- [vacant_indicators_land](../vacant_indicators_land) — a model-based view of vacancy, narrower than land use class 9.
