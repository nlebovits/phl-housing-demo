# AGENTS.md — Vacant Property Indicators — Buildings

Guidance for AI agents and LLMs working with this collection.

## Overview

Parcels the City of Philadelphia's Vacant Property Indicators model flags as likely vacant buildings.

The model was built by the Office of Innovation and Technology with Licenses and Inspections, the Office of Property Assessment, the Philadelphia Land Bank, and the Philadelphia Water Department. It reads administrative traces rather than observing the ground: a recently disconnected gas supply is one such signal, which is why a property that looks occupied from the street can still appear here.

The distribution leans low. Few parcels reach full agreement, so confident identification of a vacant building is rarer than for vacant land.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/vacant_indicators_bldg/vacant_indicators_bldg.parquet'
) LIMIT 5;
```

Coordinates are longitude and latitude in CRS84 (WGS 84). DuckDB reads
`geometry` natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `build_rank` — the model's confidence, from 0.5 to 1.0. It measures how many independent administrative signals agree, so a higher value means more agreement. It takes four values: 0.5, 0.667, 0.833, and 1.0. The "Distribution of confidence" query below counts parcels at each.
- `address` — street address. Join on this, normalized, to [dor_parcel](../dor_parcel).
- `owner1`, `owner2` — recorded owners.
- `bldg_desc` — description of the structure.
- `opa_id` — Office of Property Assessment account number.
- `lniaddresskey` — Licenses and Inspections address key.
- `councildistrict`, `zoningbasedistrict`, `zipcode` — carried through by the publisher, so aggregating by district needs no spatial join.
- `date_update` — when the model last scored this parcel.

Rank semantics come from the city data team's [post on the OpenDataPhilly forum](https://groups.google.com/g/opendataphilly/c/anMKnNH3pqc), which states that a BUILD_RANK of 0.50 or higher marks a property as likely vacant, and that "the greater the percentage value of either indicator, the more likely the property is vacant".

## Data quality & usage notes

**The `build_rank` values are repeating decimals.** They are stored as `0.5`, `0.6666666700000001`, `0.8333333300000001`, and `1.0`. Comparing with `= 0.67` or `= 0.83` silently matches nothing. Use ranges:

```sql
WHERE build_rank >= 0.8   -- not: WHERE build_rank = 0.83
```

**Every parcel here scores at least 0.5**, because that threshold is the condition for inclusion. This collection is not a census: it holds no record of parcels the model judged occupied, so you cannot compute a vacancy rate from it alone.

A flag is a model output, not a legal finding of vacancy.

`opa_id` does not join to `dor_parcel.pin`. They are identifiers from different departments and the join returns zero rows. Join on normalized address instead.

## Example queries

Distribution of confidence:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT build_rank, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_bldg/vacant_indicators_bldg.parquet')
GROUP BY 1 ORDER BY 1;
```

By council district, using the publisher's own column rather than a spatial join:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT councildistrict, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_bldg/vacant_indicators_bldg.parquet')
GROUP BY 1 ORDER BY 2 DESC;
```

Highest-confidence parcels joined to their legal boundaries:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT v.address, v.build_rank, p.basereg, p.Shape__Area
FROM read_parquet(getvariable('base') || '/vacant_indicators_bldg/vacant_indicators_bldg.parquet') v
JOIN read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet') p
  ON upper(trim(v.address)) = upper(trim(p.addr_std))
WHERE v.build_rank >= 0.95
ORDER BY p.Shape__Area DESC LIMIT 20;
```

## Versions

`vacant_indicators_bldg.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states no update cadence
([source](https://opendataphilly.org/datasets/vacant-property-indicators/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [vacant_indicators_land](../vacant_indicators_land) — vacant lots rather than vacant structures.
- [li_building_footprints](../li_building_footprints) — the physical structures.
- [affordable_housing](../affordable_housing) — `development_type = 'Rehab (unoccupied or vacant)'` records buildings returned to use.
- [dor_parcel](../dor_parcel) — join on normalized address.
