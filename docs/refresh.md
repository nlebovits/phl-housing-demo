# Scheduled refresh

`.github/workflows/refresh.yml` keeps the catalog current with the city's
ArcGIS services. Each change at the source becomes a new version. Every
earlier version stays readable, and the bucket holds one copy of each.

## Layout

Each collection has one current file and one file per earlier version:

| Path | Content | Changes |
|---|---|---|
| `<coll>/<coll>.parquet` | The current version | Every new version |
| `<coll>/<coll>.pmtiles` | Tiles for the current version | Every new version |
| `<coll>/versions/<version>.parquet` | An earlier version | Never |
| `<coll>/collection.json` | Every version: dates, row count, checksum | Every new version |

The version label is the UTC date of the extract. A forced second run on one
day gets `<date>-2`. The first version of every collection is `2026-08-26`,
the original extract.

Read the current data at the fixed URL:

```sql
SET VARIABLE base = 'https://data.source.coop/nlebovits/phl-housing-demo';
SELECT count(*) FROM read_parquet(getvariable('base') || '/dor_parcel/dor_parcel.parquet');
```

Read an earlier version at `<coll>/versions/<version>.parquet`. In
`collection.json`, the asset named after the collection is the current
version, and each `version-<version>` asset (role `archive`) is an earlier
one.

## What a run does

The workflow starts at 07:00 UTC every day. The observed source edits fall
between 11:00 and 23:00 UTC, so a run sees the full previous day.

1. `tools/refresh.py` probes each service in `tools/sources.json`. It reads
   `editingInfo.dataLastEditDate` and the `returnCountOnly` row count. That
   is two small requests per collection.
2. A collection is due when both conditions hold:
   - The source edited its rows after the current version.
   - At least `min_days` passed since the current version.
3. For each due collection, the tool extracts, repairs, and sorts the data
   (`tools/extract.py`). It then compares an order-independent hash of every
   row with the current version. Geometry is normalized before it is hashed,
   so two repairs of the same shape hash the same. Equal rows record the
   check in `state/checks.json` and publish nothing.
4. `tools/check_styles.py` checks every `match` branch and `step` class
   against the new rows. A failure holds that collection back.
5. The tool stages the upload in `data_dir`:
   - The outgoing current file, downloaded from the bucket and checked
     against the checksum `collection.json` records, as
     `versions/<old version>.parquet`.
   - The new `<coll>.parquet` and `<coll>.pmtiles`.
6. `tools/stac_versions.py` moves the old version to a `version-<version>`
   asset and records the new one as the current asset of `collection.json`.
7. The workflow runs the catalog gates. `tools/upload_data.py` uploads every
   archive before it replaces any current file. `tools/publish.py` uploads
   the metadata. The workflow then runs every documented query against the
   bucket.
8. A second job commits the published `catalog/` and `state/` to `main`.

A collection that fails at any step is rolled back. Its `catalog/` folder
and its staged files return to their state before the run. The other
collections still publish. The job then fails and opens or updates the issue
"Scheduled refresh failed".

`tools/upload_data.py` refuses to replace an object under `versions/` that
is already in the bucket, even with `--force`.

## How often each collection updates

`min_days` stops a layer that the city edits every day from publishing a
version every day. Each value comes from the publisher's stated cadence. A
dataset with no stated cadence gets 7.

| Collection | Stated cadence | `min_days` |
|---|---|---|
| `dor_parcel` | Weekly | 7 |
| `li_building_footprints` | Weekly | 7 |
| `council_districts_2024` | As needed | 1 |
| The other seven | Not stated | 7 |

The stated cadences come from the "Update Frequency" field on each
OpenDataPhilly dataset page. The seven pages without the field, and their
ArcGIS item descriptions, state no cadence. The version history records the
real cadence over time. Change a value in `tools/sources.json` when the
history shows a better one.

## Dates in the metadata

| Field | Where | Meaning |
|---|---|---|
| `version` | Each version asset, Collection | The version label |
| `created` | Each version asset | When this catalog extracted the rows |
| `phl:source_updated` | Each version asset, Collection | The source's `dataLastEditDate` for the rows |
| `updated` | Collection | When the current version was extracted |
| `phl:update_frequency` | Collection | The publisher's stated cadence, or `unstated` |
| `extent.temporal` | Collection | First to newest version |

The 2026-08-26 versions predate this pipeline, so their source edit date is
unknown. Their `phl:source_updated` is null.

## Numbers in the documentation

The READMEs and AGENTS.md files quote no numbers measured from the data. A
refresh changes the data, so a quoted count goes stale. The docs describe
what the data holds and give queries. The current row count is
`table:row_count` in each `collection.json`.

## Why there is no Iceberg table

The first version of this pipeline also kept a static Apache Iceberg table
per collection. It was removed for three reasons:

- Iceberg format v2 has no geometry type. DuckDB `iceberg_scan` with the
  spatial extension then fails on the geometry column, with "Column
  'geometry' does not have a field-id" in DuckDB 1.4.1 and "failed to cast
  column geometry from type GEOMETRY to BLOB" in 1.5.6.
- pyiceberg 0.12 cannot write format v3, which has a geometry type
  (apache/iceberg-python#1551).
- pyiceberg 0.12 cannot read a table from an `https` URL.

Revisit it when pyiceberg writes v3. The archive layout above already holds
one immutable file per version, which is what an Iceberg table would index.

## Credentials

The workflow signs in to the Source data proxy with GitHub OIDC. No key is
stored. Set this up once:

1. On source.coop, open the `nlebovits` profile, then the gear icon, then
   **Service Accounts**. Create an account.
2. Give it **Read and write** access to the `phl-housing-demo` product.
3. Under **Signs in with**, add a **GitHub workflow** for the repository
   `nlebovits/phl-housing-demo` and the environment `source-coop`.
4. In the GitHub repository settings, create the environment `source-coop`.
   Limit its deployment branches to `main`. Do not add required reviewers,
   because the daily run would wait for an approval.
5. Add a repository variable `SOURCE_SA_ID` that holds the service account
   ID.

The environment trust means a pull request job can never get write
credentials. The job requests credentials after the extract, so the
one-hour token covers only the upload.

The proxy addresses the bucket as `s3://nlebovits/phl-housing-demo` at the
endpoint `https://data.source.coop`. The workflow sets
`PUBLISH_WRITE_PREFIX` and `AWS_ENDPOINT_URL_S3` for that. A maintainer who
publishes by hand with a profile keeps the raw-bucket `write_prefix` in
`catalog.publish.yaml`.

## Running it by hand

```bash
python3 -m venv .venv
.venv/bin/pip install -r tools/requirements-refresh.txt
sudo apt-get install -y tippecanoe
export PUBLISH_DATA_DIR=../refresh-staging
.venv/bin/python3 tools/refresh.py --dry-run
.venv/bin/python3 tools/refresh.py --only dor_parcel
```

`--force` ignores `min_days` and the edit date. It still records no version
when the rows are unchanged.

An upload of a large collection takes minutes on a home connection. The
first refresh moved 1.0 GB at about 0.5 to 1.8 MB/s. Run it in the
background, or let the workflow do it.

To run the workflow by hand, use **Run workflow** on the Actions tab. The
inputs are `only`, `force`, and `dry_run`. The workflow publishes only from
`main`.

## When a run fails

- **"the bucket is at version X, which this checkout does not have"**: a
  run published and then failed to commit. Download the run's
  `refreshed-metadata` artifact, copy it over `catalog/` and `state/`, and
  commit it. Then run the refresh again.
- **"does not match the checksum of version X"**: the current file in the
  bucket changed outside the refresh. Find out what wrote it before you do
  anything else.
- **A style failure**: the new rows broke a legend. Fix the style, verify it
  against the new data, and run the refresh for that collection.
- **"the source changed mid-extract"**: the publisher edited during the
  extract. The next run retries.
