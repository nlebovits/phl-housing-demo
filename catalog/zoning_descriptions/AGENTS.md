# AGENTS.md — Zoning Code Descriptions

Guidance for AI agents and LLMs working with this collection.

## Overview

The city's own decoder for Philadelphia zoning district codes. Each row pairs a code such as `RSA-5` with its written name, "Residential Single-Family Attached-5".

This is a lookup table with no geometry. It renders no map and ships no styles. Its purpose is to make [zoning_basedistricts](../zoning_basedistricts) readable.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/zoning_descriptions/zoning_descriptions.parquet'
) LIMIT 5;
```

The table has no geometry column. Join it to `zoning_basedistricts` for
locations.

## Schema & field notes

- `new_code` — the zoning code with dashes, e.g. `CMX-2.5`. Joins to `zoning_basedistricts.long_code`.
- `code_description` — the written name.
- `objectid` — row identifier from the source service.

The codes fall into four families:

- **Residential** — RSD (single-family detached), RSA (single-family attached), RTA (two-family attached), RM (multi-family), RMX (residential mixed-use).
- **Commercial** — CA (auto-oriented), CMX (mixed-use, from neighborhood CMX-1 to Center City core CMX-5).
- **Industrial** — I-1 light, I-2 medium, I-3 heavy, I-P port, plus ICMX and IRMX mixed-use variants.
- **Special purpose** — SP-AIR airport, SP-INS institutional, SP-ENT entertainment, SP-STA stadium, SP-PO-A and SP-PO-P active and passive open space, SP-CIV civic/educational/medical.

## Data quality & usage notes

No geometry column, so this collection is tabular. Spatial functions do not apply.

Covers base district codes only. Overlay symbols live in [zoning_overlays](../zoning_overlays) and are not decoded here.

The table was written with DuckDB rather than `portolan extract`, which reports "0/0 layers" for ArcGIS services advertising a table instead of a layer. See [portolan-cli#812](https://github.com/portolan-sdi/portolan-cli/issues/812). Every row of the 2026-08-26 extract was verified against the source.

## Example queries

The whole table is small enough to read at once:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT new_code, code_description
FROM read_parquet(getvariable('base') || '/zoning_descriptions/zoning_descriptions.parquet')
ORDER BY new_code;
```

Label a zoning map. Every district polygon matches:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT d.code_description, count(*) AS polygons
FROM read_parquet(getvariable('base') || '/zoning_basedistricts/zoning_basedistricts.parquet') z
JOIN read_parquet(getvariable('base') || '/zoning_descriptions/zoning_descriptions.parquet') d
  ON z.long_code = d.new_code
GROUP BY 1 ORDER BY 2 DESC;
```

Residential codes only:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT new_code, code_description
FROM read_parquet(getvariable('base') || '/zoning_descriptions/zoning_descriptions.parquet')
WHERE code_description LIKE 'Residential%'
ORDER BY new_code;
```

## Versions

`zoning_descriptions.parquet` is always the current extract. Each earlier extract stays at
`versions/<version>.parquet` and never changes. `collection.json` lists every
version, with its checksum and the date the city last edited the rows.
`2026-08-26` is the first version. The publisher states no update cadence
([source](https://opendataphilly.org/datasets/zoning-descriptions/)). The catalog checks the source daily and
records a new version at most every 7 days, and only when the rows changed.
See "Versions" in the [catalog guide](../AGENTS.md) for a query that
compares two versions.

## Related collections

- [zoning_basedistricts](../zoning_basedistricts) — the polygons this table labels.
- [zoning_overlays](../zoning_overlays) — overlay rules, which use a separate symbol vocabulary.
