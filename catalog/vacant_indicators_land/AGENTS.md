# AGENTS.md — Vacant Property Indicators — Land

Guidance for AI agents and LLMs working with this collection.

## Overview

Parcels the City of Philadelphia's Vacant Property Indicators model flags as likely vacant land. 28,737 parcels.

The model was built by the Office of Innovation and Technology with Licenses and Inspections, the Office of Property Assessment, the Philadelphia Land Bank, and the Philadelphia Water Department. It reads administrative traces rather than observing the ground: a recently disconnected gas supply is one such signal, which is why a property that looks occupied from the street can still appear here.

8,413 parcels score 1.0, where every indicator agrees the lot is empty.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/vacant_indicators_land/vacant_indicators_land.parquet'
) LIMIT 5;
```

Coordinates are EPSG:3857 (Web Mercator) metres. DuckDB reads `geometry`
natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `land_rank` — the model's confidence, from 0.5 to 1.0. It measures how many independent administrative signals agree, so a higher value means more agreement. Distribution: 0.5 (16,294 parcels), 0.667 (3,635), 0.833 (395), 1.0 (8,413).
- `address` — street address. Join on this, normalized, to [dor_parcel](../dor_parcel).
- `owner1`, `owner2` — recorded owners.
- `bldg_desc` — description of the structure.
- `opa_id` — Office of Property Assessment account number.
- `lniaddresskey` — Licenses and Inspections address key.
- `councildistrict`, `zoningbasedistrict`, `zipcode` — carried through by the publisher, so aggregating by district needs no spatial join.
- `date_update` — when the model last scored this parcel.

Rank semantics come from the city data team's [post on the OpenDataPhilly forum](https://groups.google.com/g/opendataphilly/c/anMKnNH3pqc), which states that a LAND_RANK of 0.50 or higher marks a property as likely vacant, and that "the greater the percentage value of either indicator, the more likely the property is vacant".

## Data quality & usage notes

**The `land_rank` values are repeating decimals.** They are stored as `0.5`, `0.6666666700000001`, `0.8333333300000001`, and `1.0`. Comparing with `= 0.67` or `= 0.83` silently matches nothing. Use ranges:

```sql
WHERE land_rank >= 0.8   -- not: WHERE land_rank = 0.83
```

**Every parcel here scores at least 0.5**, because that threshold is the condition for inclusion. This collection is not a census: it holds no record of parcels the model judged occupied, so you cannot compute a vacancy rate from it alone.

A flag is a model output, not a legal finding of vacancy.

`opa_id` does not join to `dor_parcel.pin`. They are identifiers from different departments and the join returns zero rows. Join on normalized address instead.

## Example queries

Distribution of confidence:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT land_rank, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet')
GROUP BY 1 ORDER BY 1;
```

By council district, using the publisher's own column rather than a spatial join:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT councildistrict, count(*) AS parcels
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet')
GROUP BY 1 ORDER BY 2 DESC;
```

Highest-confidence parcels joined to their legal boundaries:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT v.address, v.land_rank, p.basereg, p.Shape__Area
FROM read_parquet(getvariable('base') || '/vacant_indicators_land/vacant_indicators_land.parquet') v
JOIN read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet') p
  ON upper(trim(v.address)) = upper(trim(p.addr_std))
WHERE v.land_rank >= 0.95
ORDER BY p.Shape__Area DESC LIMIT 20;
```

## Related collections

- [vacant_indicators_bldg](../vacant_indicators_bldg) — vacant structures rather than vacant lots.
- [dor_parcel](../dor_parcel) — join on normalized address, 96% match rate.
- [land_use](../land_use) — class 9 is the planning department's own vacancy assessment, broader than this model's.
- [council_districts_2024](../council_districts_2024) — District 5 holds 9,178 vacant parcels against 268 in District 10.
