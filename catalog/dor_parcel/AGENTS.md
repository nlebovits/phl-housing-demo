# AGENTS.md — Property Parcels

Guidance for AI agents and LLMs working with this collection.

## Overview

Boundaries of every real estate property parcel in Philadelphia, drawn from recorded deed documents by the Department of Records. One polygon per parcel, republished weekly at the source.

Use this collection when you need the legal footprint of a property, or as the spatial base for anything keyed to an address.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/dor_parcel/dor_parcel.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

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

- `condoflag` — 1 for a condominium parcel, 0 otherwise, null on some rows.
- `elev_flag`, `topelev`, `botelev` — elevation bounds for stacked parcels, where several parcels occupy the same ground at different heights.
- `orig_date`, `inactdate` — creation and inactivation timestamps.

**Undocumented columns.** `muniment_type`, `muniment_id`, `separated_rights`, `dor_review`, `opa_review`, `pwd_review`, `matchflag`, and the integer `status` have no published meaning. Their ArcGIS field aliases repeat the column name and the city metadata portal exposes no reachable data dictionary. `status` holds the codes 1, 2, 3, 4, 5, and 9, and is null on some rows. What those codes mean is not stated anywhere the publisher has released. Treat them as opaque, and count them yourself:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT status, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet')
GROUP BY 1 ORDER BY 1;
```

## Data quality & usage notes

Some rows have null geometry. They carry attributes but cannot be mapped, and they sort to the end of the file. Filter them with `WHERE geometry IS NOT NULL`.

Invalid geometries were repaired with `shapely.make_valid` during the 2026-08-26 extraction. No invalid geometry remains.

`Shape__Area` is in Web Mercator square metres, so it overstates ground area by roughly 1.7x at Philadelphia's latitude. Reproject to EPSG:2272 for real areas.

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

## Versions

`dor_parcel.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states a weekly update cadence
([source](https://opendataphilly.org/datasets/department-of-records-property-parcels/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [land_use](../land_use) — what is happening on the parcel.
- [li_building_footprints](../li_building_footprints) — structures standing on it.
- [vacant_indicators_land](../vacant_indicators_land) and [vacant_indicators_bldg](../vacant_indicators_bldg) — join on `upper(trim(addr_std))` to their `address`, which matches most vacancy rows.
- [zoning_basedistricts](../zoning_basedistricts) — what the code permits, joined spatially.
