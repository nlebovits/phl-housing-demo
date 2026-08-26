# AGENTS.md — repository guidance

This file is about working on the repository. For working with the data, read
[catalog/AGENTS.md](catalog/AGENTS.md), which publishes.

## What this repository is

The metadata for the [Philadelphia Housing and Land
Use](https://source.coop/nlebovits/phl-housing-demo) catalog: STAC JSON, map
styles, thumbnails, and documentation for ten collections mirrored from the
City of Philadelphia's ArcGIS services.

The data itself lives in the bucket and never in git.

## Two publishers, and they do not interoperate

This catalog has two upload paths, and mixing them corrupts the version state.

**`portolan push` owns the data assets.** GeoParquet and PMTiles were uploaded
with it, and it records every upload in `versions.json` keyed on sha256. It
runs from the working catalog outside this repository, not from `catalog/`.

**`tools/publish.py` owns the metadata under `catalog/`.** It keeps no state
and compares local size and MD5 against the bucket listing.

Never run `portolan push` from this repository, and never point
`tools/publish.py` at a data directory. The version history in `versions.json`
is only correct if the tool that wrote it is the tool that updates it.

## The publish boundary

`catalog/` is the published catalog. Everything in it is published, and nothing
outside it ever is. Do not move a file into `catalog/` to make it publish, and
do not add a path outside `publish_dir` to `tools/publish.py`.

## Data never enters git

Never commit a GeoParquet, COG, PMTiles, Zarr, or COPC file. `.gitignore`
blocks the common suffixes. Thumbnails are the deliberate exception: they are
small, they let the repository render, and they are the artifact most likely to
need review in a pull request.

## Every documented query has to run

`tests/test_queries.py` extracts every SQL block from the `AGENTS.md` files
under `catalog/` and runs it against the published bucket. A recipe that fails
on the first try is worse than no recipe, because it costs the reader the time
to debug someone else's mistake.

Queries read the published URLs through a `SET VARIABLE base` prelude, so they
run as written from anywhere. Do not rewrite them to relative paths; those
resolve only for a reader who has already downloaded the catalog.

Set `QUERY_CHECK_REMOTE=0` to skip the network and run the rest.

## Claims carry their source

Every claim in a `catalog/**/AGENTS.md` is quoted from a source or measured
from the data. An invented join key or column name produces a confident wrong
answer that nothing downstream catches.

Three findings in this catalog came from outside the service metadata and are
cited where they are used: the building FCODE key from the
[PASDA metadata record](https://www.pasda.psu.edu/uci/FullMetadataDisplay.aspx?file=PhiladelphiaBuildings2017.xml),
the vacancy rank semantics from the city data team's
[forum post](https://groups.google.com/g/opendataphilly/c/anMKnNH3pqc), and
the land use labels derived from the data with a recorded query.

## Styles are verified against the data

Every `match` branch and `step` boundary in `catalog/**/styles/*.json` was
checked against a query on the published data. A legend listing categories the
data lacks is the most common visible defect in a new catalog, and this one
shipped with three of them before they were caught.

Re-verify after changing a style. A branch that matches nothing paints its
features with the fallback colour while the legend claims otherwise.

Two specific traps in this data:

- Vacancy ranks are repeating decimals (`0.6666666700000001`). A `match` on
  `0.67` matches nothing. Use `step`.
- Land use codes 52, 72, 81, 91, and 92 are easy to omit. Code 91 alone covers
  36,646 parcels.

## The conformance allow-list

`ACCEPTED` in `tests/test_conformance.py` ships empty. Never add an entry
without a matching row in `docs/conformance.md` giving the rule, where it
fires, why it is accepted, and the issue tracking its removal.

## Running the gates

```bash
python3 -m venv .venv
.venv/bin/pip install 'rashid>=0.1.5,<0.2.0' stac-check
.venv/bin/python3 tests/run_all.py
```

Run through the virtualenv interpreter so the gates find the rashid you chose
rather than whatever is on PATH.
