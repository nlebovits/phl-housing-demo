# AGENTS.md — Building Footprints

Guidance for AI agents and LLMs working with this collection.

## Overview

Outlines of buildings and related structures, captured photogrammetrically from aerial imagery. 546,083 polygons covering residential, commercial, and industrial buildings, plus isolated garages, mobile homes, sheds, greenhouses, silos, and buildings under construction that have walls.

Structures under 150 square feet are generally not captured.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/li_building_footprints/li_building_footprints.parquet'
) LIMIT 5;
```

Coordinates are EPSG:3857 (Web Mercator) metres. DuckDB reads `geometry`
natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `bin` — Building Identification Number. Unique across all 546,083 rows, so it is a safe primary key.
- `fcode` — feature code. The published key defines `1810 = Building` (545,339 rows) and `1830 = Tank` (61 rows). 683 rows carry `0`, which the key does not define.
- `approx_hgt` — approximate height in feet above base. Median around 24.
- `max_hgt` — maximum elevation of non-ground points within the footprint, minus the base measurement.
- `base_elevation` — ground elevation at the footprint.
- `square_ft` — footprint area in square feet, computed by the publisher. Prefer this to `Shape__Area`, which is distorted Web Mercator metres.
- `address`, `dor_alternate_addr` — street address and an alternate form.
- `building_name` — populated only for named buildings.
- `parcel_id_num`, `parcel_id_source` — a parcel identifier and the department it came from. Every populated row shows `PWD`, the Water Department, so this does **not** join to `dor_parcel`.

The FCODE key is published in the [PASDA metadata record](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaBuildings2017.xml).

## Data quality & usage notes

683 rows carry `fcode = 0`, undefined in the published key.

235 rows have null `approx_hgt`. The height style places them in the lowest bin rather than dropping them, so a map shows them.

Height distribution: 57,606 under 20 ft, 427,111 between 20 and 35 ft, 58,494 between 35 and 60 ft, and 2,637 at 60 ft or above.

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

## Related collections

- [dor_parcel](../dor_parcel) — parcel boundaries. Join spatially or on address; `parcel_id_num` is a Water Department identifier and will not match.
- [vacant_indicators_bldg](../vacant_indicators_bldg) — which of these structures the city believes are empty.
- [land_use](../land_use) — what the building is used for.
