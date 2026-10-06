#!/usr/bin/env python3
"""Refresh the catalog from its ArcGIS sources, one version per change.

For each collection in ``tools/sources.json``:

1. Probe the service: ``dataLastEditDate`` and ``returnCountOnly``.
2. Skip it unless it is due. A collection is due when the source edited its
   rows after the current version (or the last no-op check), and at least
   ``min_days`` have passed since the current version. ``min_days`` comes
   from the publisher's stated cadence, so a layer the city touches daily
   but publishes weekly gets a version at most weekly.
3. Extract, repair and sort (``tools/extract.py``). Skip the version when
   the row content hash equals the current one.
4. Check the styles against the new rows (``tools/check_styles.py``).
5. Stage the upload in ``data_dir``:
   - the outgoing current file at ``<coll>/versions/<version>.parquet``,
     downloaded and checked against the checksum the Collection records
   - the new ``<coll>/<coll>.parquet`` and ``<coll>/<coll>.pmtiles``
6. Record the new version in ``collection.json`` (``tools/stac_versions.py``).

A collection that fails at any step is rolled back: its ``catalog/`` folder
and its staged files return to their state before the run. The others go on.
Nothing here uploads. The workflow runs the gates, then ``upload_data.py``
(archives first) and ``publish.py``.

    python3 tools/refresh.py --dry-run          # what is due, and why
    python3 tools/refresh.py                    # refresh what is due
    python3 tools/refresh.py --only dor_parcel --force
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import traceback
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import arcgis  # noqa: E402
import check_styles  # noqa: E402
import extract as extractor  # noqa: E402
import stac_versions as stac  # noqa: E402
from publish import ROOT, load_config  # noqa: E402

STATE = ROOT / "state" / "checks.json"
USER_AGENT = "phl-housing-demo-refresh (+https://github.com/nlebovits/phl-housing-demo)"


def parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load_state() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save_state(state: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")


def decide(collection: str, entry: dict, probe: arcgis.SourceState,
           current: dict | None, state: dict, now: datetime) -> tuple[bool, str]:
    """Whether a collection is due, and a sentence saying why.

    ``current`` is the current version asset of the Collection, or None.
    """
    if current is None:
        return True, "no version yet"
    known = max(filter(None, [
        current.get("phl:source_updated"),
        state.get(collection, {}).get("source_updated"),
    ]), default=None)
    if known and probe.data_last_edit <= known:
        return False, f"source unchanged since {known}"
    last = parse(current["created"])
    due = last + timedelta(days=entry["min_days"])
    if now < due:
        return False, (f"source edited {probe.data_last_edit}, but the current "
                       f"version is {last:%Y-%m-%d}; next due {due:%Y-%m-%d}")
    return True, f"source edited {probe.data_last_edit}"


def download(url: str, out: Path) -> None:
    """Fetch a public object. data.source.coop answers 403 to urllib's
    default User-Agent, so the request names this tool."""
    out.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=600) as response, \
            out.open("wb") as fh:
        shutil.copyfileobj(response, fh)


def make_pmtiles(parquet: Path, out: Path, layer: str) -> None:
    """Build PMTiles the way ``portolan add --pmtiles`` built the originals.

    tippecanoe writes a progress line per tile to the inherited stderr, tens
    of kilobytes for one small layer. The output goes to a file and is shown
    only when the build fails.
    """
    import os

    from geoparquet_io.api.ops import create_pmtiles

    with tempfile.TemporaryFile() as log:
        saved = os.dup(2), os.dup(1)
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(log.fileno(), 2)
        os.dup2(log.fileno(), 1)
        try:
            create_pmtiles(str(parquet), str(out), layer=layer, force=True)
        except Exception as exc:
            log.seek(0)
            tail = log.read().decode(errors="replace")[-3000:]
            raise RuntimeError(f"PMTiles build failed: {exc}\n{tail}") from exc
        finally:
            os.dup2(saved[0], 2)
            os.dup2(saved[1], 1)
            os.close(saved[0])
            os.close(saved[1])


class Context:
    def __init__(self, config: dict, sources: dict, now: datetime):
        self.public_base = config["public_base"].rstrip("/")
        self.catalog = ROOT / config["publish_dir"]
        data_dir = config.get("data_dir")
        if not data_dir:
            sys.exit("set data_dir in catalog.publish.yaml or PUBLISH_DATA_DIR")
        self.data = (ROOT / data_dir).resolve()
        self.sources = sources
        self.now = now
        self.stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")


def published_version(ctx: Context, collection: str) -> str | None:
    """The ``version`` of the published Collection, or None."""
    url = f"{ctx.public_base}/{collection}/collection.json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response).get("version")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def assert_in_sync(ctx: Context, collection: str) -> None:
    """Refuse to run when the bucket holds a version git does not.

    That happens when a run published and then failed to commit. A refresh
    from the older checkout would archive the wrong file under the wrong
    label, and the bucket and git would disagree about history.
    """
    remote = published_version(ctx, collection)
    if remote is not None and remote not in stac.versions(ctx.catalog, collection):
        raise RuntimeError(
            f"{collection}: the bucket is at version {remote}, which this "
            "checkout does not have. Commit the published catalog/ state "
            "before refreshing again."
        )


def archive_current(ctx: Context, collection: str, asset: dict) -> Path:
    """Stage the outgoing current file as ``versions/<version>.parquet``.

    The bytes come from the public URL and must match the checksum the
    Collection records, so the archive is exactly what readers had.
    """
    label = asset["version"]
    out = stac.archive_path(ctx.data, collection, label)
    if not out.exists():
        download(asset["href"], out)
    if stac.multihash(out) != asset["file:checksum"]:
        out.unlink()
        raise RuntimeError(
            f"{collection}: {asset['href']} does not match the checksum of "
            f"version {label}; the published file changed outside the refresh"
        )
    return out


def refresh_one(ctx: Context, collection: str, probe: arcgis.SourceState,
                state: dict) -> str:
    entry = ctx.sources["collections"][collection]
    assert_in_sync(ctx, collection)
    now = stac.current(ctx.catalog, collection)
    previous = stac.current_href(ctx.public_base, collection) if now else None

    with tempfile.TemporaryDirectory(prefix=f"refresh-{collection}-") as tmp:
        new = Path(tmp) / f"{collection}.parquet"
        result = extractor.extract(collection, new, ctx.sources)
        if now and result.content_hash == now.get("phl:content_hash"):
            state[collection] = {"source_updated": probe.data_last_edit,
                                 "checked": ctx.stamp}
            return f"rows unchanged since version {now['version']}"

        problems = check_styles.check(collection, str(new), previous, ctx.catalog)
        if problems:
            raise StyleError(problems)

        if now:
            archive_current(ctx, collection, now)
        label = stac.next_version(ctx.catalog, collection, ctx.stamp[:10])
        current = ctx.data / collection / f"{collection}.parquet"
        current.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(new, current)

    pmtiles = None
    if entry["kind"] == "layer":
        pmtiles = ctx.data / collection / f"{collection}.pmtiles"
        make_pmtiles(current, pmtiles, collection)

    stac.add_version(
        catalog=ctx.catalog, collection=collection, version=label,
        parquet=current, pmtiles=pmtiles, public_base=ctx.public_base,
        source_updated=probe.data_last_edit, created=ctx.stamp,
        extra={"phl:content_hash": result.content_hash,
               "phl:repaired_geometries": result.repaired,
               "phl:null_geometries": result.null_geometries},
        update_frequency=entry["update_frequency"],
        frequency_source=entry["frequency_source"],
    )
    state.pop(collection, None)
    return f"version {label}: {result.rows} rows"


class StyleError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__("\n".join(problems))
        self.problems = problems


def guarded(ctx: Context, collection: str, probe, state: dict) -> dict:
    """refresh_one, with the collection rolled back if it raises."""
    folder = ctx.catalog / collection
    staged = ctx.data / collection
    with tempfile.TemporaryDirectory() as tmp:
        saved_catalog = Path(tmp) / "catalog"
        shutil.copytree(folder, saved_catalog)
        saved_data = Path(tmp) / "data"
        if staged.exists():
            shutil.copytree(staged, saved_data)
        try:
            return {"status": "ok", "detail": refresh_one(ctx, collection, probe, state)}
        except Exception as exc:  # noqa: BLE001 - report, roll back, go on
            shutil.rmtree(folder)
            shutil.copytree(saved_catalog, folder)
            shutil.rmtree(staged, ignore_errors=True)
            if saved_data.exists():
                shutil.copytree(saved_data, staged)
            kind = "style" if isinstance(exc, StyleError) else "error"
            detail = str(exc) if kind == "style" else traceback.format_exc()
            return {"status": kind, "detail": detail}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--only", help="comma-separated collection ids")
    parser.add_argument("--force", action="store_true",
                        help="ignore min_days and the source edit date")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what is due and stop")
    parser.add_argument("--report", type=Path,
                        help="write the outcome per collection as JSON")
    args = parser.parse_args()

    config = load_config()
    sources = arcgis.load_sources()
    ctx = Context(config, sources, datetime.now(timezone.utc))
    names = sorted(sources["collections"])
    if args.only:
        names = [n.strip() for n in args.only.split(",")]
        unknown = set(names) - set(sources["collections"])
        if unknown:
            sys.exit(f"unknown collection(s): {', '.join(sorted(unknown))}")

    state = load_state()
    report: dict[str, dict] = {}
    for name in names:
        probe = arcgis.probe(sources, name)
        due, why = decide(name, sources["collections"][name], probe,
                          stac.current(ctx.catalog, name), state, ctx.now)
        if args.force:
            due, why = True, f"forced; {why}"
        print(f"{'DUE ' if due else 'skip'} {name:24} {why}", flush=True)
        if not due or args.dry_run:
            report[name] = {"status": "due" if due else "skipped", "detail": why}
            continue
        report[name] = guarded(ctx, name, probe, state)
        print(f"     {name:24} {report[name]['status']}: "
              f"{report[name]['detail'].splitlines()[0]}", flush=True)

    if not args.dry_run:
        save_state(state)
    if args.report:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    failed = [n for n, r in report.items() if r["status"] in ("style", "error")]
    for name in failed:
        print(f"\n--- {name} ({report[name]['status']})\n{report[name]['detail']}",
              file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
