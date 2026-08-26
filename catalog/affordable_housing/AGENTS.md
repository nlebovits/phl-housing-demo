# AGENTS.md — Affordable Housing Production

Guidance for AI agents and LLMs working with this collection.

## Overview

Affordable housing projects funded by the Division of Housing and Community Development and completed since 1994. 501 projects accounting for 19,249 units, spanning fiscal years 1995 through 2026.

This is the only point collection in the catalog.

## Accessing the data

```sql
INSTALL spatial; LOAD spatial;
INSTALL httpfs; LOAD httpfs;

SELECT * FROM read_parquet(
  'https://data.source.coop/nlebovits/phl-housing-demo/affordable_housing/affordable_housing.parquet'
) LIMIT 5;
```

Coordinates are EPSG:3857 (Web Mercator) metres. DuckDB reads `geometry`
natively, so do not wrap it in `ST_GeomFromWKB`.

## Schema & field notes

- `project_name`, `developer_name`, `address` — who built what, and where.
- `fiscal_year_complete` — fiscal year of completion, 1995 to 2026.
- `total_units` — units delivered. Sums to 19,249.
- `accessible_units`, `sensory_units`, `visitable_units` — accessibility counts within the total.
- `project_type` — Rental, Special Needs, Homeownership, Mixed Use, **or a semicolon-joined combination** such as `Rental;Special Needs;Mixed Use`.
- `development_type` — New Construction, Rehab (unoccupied or vacant), or Preservation (occupied). Also semicolon-joined in places.
- `status` — Complete or Under Construction.

## Data quality & usage notes

**`project_type` and `development_type` hold multiple values separated by semicolons.** Grouping on the raw column treats each combination as its own category, which undercounts: naive grouping reports 242 rental projects, while splitting on `;` gives the true 262.

**Both columns mix three kinds of missing value**: a real SQL null, the literal string `'null'`, and the literal string `'NULL'`. Filter all three.

25 of 501 projects have null geometry. They carry attributes but cannot be mapped, and they sort to the end of the file.

The dataset covers DHCD-funded projects only. Affordable housing built without DHCD funding does not appear, so this is not a complete picture of affordable housing in the city.

## Example queries

Correct project-type counts, splitting the semicolon-joined values:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT trim(t) AS project_type, count(*) AS projects
FROM read_parquet(getvariable('base') || '/affordable_housing/affordable_housing.parquet'),
     UNNEST(string_split(project_type, ';')) AS s(t)
WHERE project_type IS NOT NULL
  AND project_type NOT IN ('null', 'NULL')
GROUP BY 1 ORDER BY 2 DESC;
```

Units delivered per fiscal year:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT fiscal_year_complete, sum(total_units) AS units, count(*) AS projects
FROM read_parquet(getvariable('base') || '/affordable_housing/affordable_housing.parquet')
GROUP BY 1 ORDER BY 1;
```

Accessibility share of the portfolio:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT sum(total_units) AS units,
       sum(accessible_units) AS accessible,
       round(100.0 * sum(accessible_units) / sum(total_units), 1) AS pct
FROM read_parquet(getvariable('base') || '/affordable_housing/affordable_housing.parquet');
```

Projects that returned vacant buildings to use:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';

SELECT project_name, address, total_units, fiscal_year_complete
FROM read_parquet(getvariable('base') || '/affordable_housing/affordable_housing.parquet')
WHERE development_type LIKE '%Rehab%'
ORDER BY total_units DESC;
```

## Related collections

- [vacant_indicators_bldg](../vacant_indicators_bldg) — the vacant-building stock that rehabilitation projects draw from.
- [council_districts_2024](../council_districts_2024) — join spatially to see where production has landed.
- [zoning_basedistricts](../zoning_basedistricts) — what the code permits where projects were built.
