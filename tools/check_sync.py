#!/usr/bin/env python3
"""Refuse to publish when the bucket holds a version that git does not.

That happens when a refresh published and then failed to commit. A publish
from the older checkout would replace the newer collection.json in the
bucket, and the bucket would point at versions it no longer describes.

The refresh calls ``ahead_of`` before it extracts a collection. The publish
workflow runs this script before it uploads ``catalog/``.

    python3 tools/check_sync.py

Exits 1 and names each collection whose published version is unknown to
this checkout. Needs network access to the public base URL.
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import stac_versions as stac  # noqa: E402
from publish import ROOT, load_config  # noqa: E402

USER_AGENT = "phl-housing-demo-refresh (+https://github.com/nlebovits/phl-housing-demo)"


def published_version(public_base: str, collection: str) -> str | None:
    """The ``version`` of the published Collection, or None."""
    url = f"{public_base}/{collection}/collection.json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response).get("version")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def ahead_of(catalog: Path, public_base: str, collection: str) -> str | None:
    """The published version when git does not have it, else None."""
    remote = published_version(public_base, collection)
    if remote is not None and remote not in stac.versions(catalog, collection):
        return remote
    return None


def main() -> int:
    config = load_config()
    catalog = ROOT / config["publish_dir"]
    base = config["public_base"].rstrip("/")
    names = sorted(p.parent.name for p in catalog.glob("*/collection.json"))
    ahead = {n: v for n in names if (v := ahead_of(catalog, base, n))}
    for name, version in ahead.items():
        print(f"error  {name}: the bucket is at version {version}, which this "
              "checkout does not have", file=sys.stderr)
    if ahead:
        print("Commit the published catalog/ state before publishing again. "
              "See AGENTS.md.", file=sys.stderr)
        return 1
    print(f"OK: git has every published version of {len(names)} collection(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
