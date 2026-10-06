# AGENTS.md — Building Footprints

Guidance for AI agents and LLMs working with this collection.

## Overview

Outlines of buildings and related structures, captured photogrammetrically from aerial imagery. The polygons cover residential, commercial, and industrial buildings, plus isolated garages, mobile homes, sheds, greenhouses, silos, and buildings under construction that have walls.

Structures under 150 square feet are generally not captured.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/li_building_footprints/li_building_footprints.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `bin` — Building Identification Number. Unique across all rows, so it is a safe primary key.
- `fcode` — feature code. The published key defines `1810 = Building` and `1830 = Tank`. Nearly every row is a building. A small share of rows carry `0`, which the key does not define.
- `approx_hgt` — approximate height in feet above base.
- `max_hgt` — maximum elevation of non-ground points within the footprint, minus the base measurement.
- `base_elevation` — ground elevation at the footprint.
- `square_ft` — footprint area in square feet, computed by the publisher. Prefer this to `Shape__Area`, which is distorted Web Mercator metres.
- `address`, `dor_alternate_addr` — street address and an alternate form.
- `building_name` — populated only for named buildings.
- `parcel_id_num`, `parcel_id_source` — a parcel identifier and the department it came from, `PWD` (Water Department) or `DOR` (Department of Records). It rarely matches `dor_parcel.basereg`, so it does **not** join to `dor_parcel`.

The FCODE key is published in the [PASDA metadata record](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaBuildings2017.xml).

## Data quality & usage notes

A small share of rows carry `fcode = 0`, undefined in the published key.

A few rows have null `approx_hgt`. Filter them with `WHERE approx_hgt IS NOT NULL` before you analyse height.

The height style breaks at 20, 35, and 60 ft. Most buildings fall between 20 and 35 ft, and few reach 60 ft or above.

Tippecanoe dropped features from z10 and z11 tiles to stay under its 200,000-feature limit. The GeoParquet holds every feature, and the PMTiles are complete from z12 up.

## Example queries

Tallest buildings:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT building_name, address, approx_hgt, square_ft
FROM read_parquet(getvariable('base') || '/li_building_footprints/li_building_footprints.parquet')
WHERE approx_hgt IS NOT NULL
ORDER BY approx_hgt DESC LIMIT 20;
```

Built floor area by council district, using the publisher's own square footage:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c.district, sum(b.square_ft) AS total_sq_ft, count(*) AS buildings
FROM read_parquet(getvariable('base') || '/li_building_footprints/li_building_footprints.parquet') b
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, ST_Centroid(b.geometry))
GROUP BY 1 ORDER BY 2 DESC;
```

Tanks rather than buildings:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT bin, address, approx_hgt, square_ft
FROM read_parquet(getvariable('base') || '/li_building_footprints/li_building_footprints.parquet')
WHERE fcode = 1830
ORDER BY square_ft DESC;
```

## Versions

`li_building_footprints.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states a weekly update cadence
([source](https://opendataphilly.org/datasets/building-footprints/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [dor_parcel](../dor_parcel) — parcel boundaries. Join spatially or on address. `parcel_id_num` rarely matches `dor_parcel.basereg`.
- [vacant_indicators_bldg](../vacant_indicators_bldg) — which of these structures the city believes are empty.
- [land_use](../land_use) — what the building is used for.
