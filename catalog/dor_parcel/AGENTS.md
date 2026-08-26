# AGENTS.md — Property Parcels

Guidance for AI agents and LLMs working with this collection.

## Overview

Boundaries of every real estate property parcel in Philadelphia, drawn from recorded deed documents by the Department of Records. 607,957 polygons, republished weekly at the source.

Use this collection when you need the legal footprint of a property, or as the spatial base for anything keyed to an address.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/dor_parcel/dor_parcel.parquet'
) LIMIT 5;
```

Coordinates are EPSG:3857 (Web Mercator) metres. DuckDB reads `geometry`
natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

Identifiers:

- `basereg`, `mapreg` — Base and Map Registry Number, the Department of Records' own identifiers. `basereg` looks like `037S100005`.
- `recmap`, `recsub`, `parcel` — Registry Map, Sub Map, and Parcel Number, the components `basereg` is built from.
- `pin` — Parcel Identification Number, an integer.
- `geoid` — Geographic Unique ID. Null on every row in this extract.

Address, parsed into components:

- `house`, `stex` — house number and its extension (the `27` and `29` of `27-29`).
- `stdir`, `stnam`, `stdes`, `stdessuf` — direction, name, designation, suffix.
- `addr_std` — the standardized single-string address. Use this for joins.
- `addr_source` — where the standardized address came from.

Structure flags:

- `condoflag` — 1 for a condominium parcel (3,497 rows), 0 otherwise (604,131), null on 329.
- `elev_flag`, `topelev`, `botelev` — elevation bounds for stacked parcels, where several parcels occupy the same ground at different heights.
- `orig_date`, `inactdate` — creation and inactivation timestamps.

**Undocumented columns.** `muniment_type`, `muniment_id`, `separated_rights`, `dor_review`, `opa_review`, `pwd_review`, `matchflag`, and the integer `status` have no published meaning. Their ArcGIS field aliases repeat the column name and the city metadata portal exposes no reachable data dictionary. `status` holds 1 (571,350 rows), 2 (33,856), 3 (2,722), 4 (7), 5 (6), and null (11); what those codes mean is not stated anywhere the publisher has released. Treat them as opaque.

## Data quality & usage notes

37 of 607,957 rows have null geometry. They carry attributes but cannot be mapped, and they sort to the end of the file.

4 invalid geometries were repaired with `shapely.make_valid` during extraction. No invalid geometry remains.

`Shape__Area` is in Web Mercator square metres, so it overstates ground area by roughly 1.7x at Philadelphia's latitude. Measured quartiles are 150.3, 216.9, and 364.3, with the 95th percentile at 1,462.0. Reproject to EPSG:2272 for real areas.

`pin` does **not** join to `opa_id` in the vacancy collections. They are identifiers from different city departments and the join returns zero rows.

## Example queries

Find a parcel by address:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT basereg, addr_std, condoflag, Shape__Area
FROM read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet')
WHERE addr_std ILIKE '%BROAD ST%'
LIMIT 10;
```

Condominium parcels by council district, using a spatial join:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT c.district, count(*) AS condo_parcels
FROM read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet') p
JOIN read_parquet(getvariable('base') || '/council_districts_2024/council_districts_2024.parquet') c
  ON ST_Intersects(c.geometry, ST_Centroid(p.geometry))
WHERE p.condoflag = 1
GROUP BY 1 ORDER BY 2 DESC;
```

Stacked parcels, where several properties share ground at different elevations:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT basereg, addr_std, topelev, botelev
FROM read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet')
WHERE elev_flag = 1
LIMIT 10;
```

## Related collections

- [land_use](../land_use) — what is happening on the parcel.
- [li_building_footprints](../li_building_footprints) — structures standing on it.
- [vacant_indicators_land](../vacant_indicators_land) and [vacant_indicators_bldg](../vacant_indicators_bldg) — join on `upper(trim(addr_std))` to their `address`, which matches 96% of vacancy rows.
- [zoning_basedistricts](../zoning_basedistricts) — what the code permits, joined spatially.
