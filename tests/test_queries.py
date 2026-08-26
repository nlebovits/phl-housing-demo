"""Every SQL block in the catalog's AGENTS.md files has to run.

A recipe that fails on the first try costs the reader the time to debug someone
else's mistake, so this gate runs each one and fails on any error.

Queries that read the published bucket over HTTP are the point of the check:
they catch a moved asset, a renamed column, or a stale URL before a reader
does. They need network access, so set QUERY_CHECK_REMOTE=0 to skip them and
run only the ones that read local files.

Blocks are skipped when they are illustrative fragments rather than runnable
statements: anything opening with WHERE, or a bash/python fence.
"""

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "catalog"
REMOTE_PREFIX = "https://data.source.coop/"

SETUP = "INSTALL spatial; LOAD spatial;\nINSTALL httpfs; LOAD httpfs;\n"
TIMEOUT = 900


def sql_blocks():
    """Yield (label, sql, is_remote) for every runnable block."""
    files = sorted(CATALOG.glob("*/AGENTS.md")) + [CATALOG / "AGENTS.md"]
    for md in files:
        if not md.exists():
            continue
        text = md.read_text()
        for i, m in enumerate(re.finditer(r"```sql\n(.*?)```", text, re.S)):
            sql = m.group(1).strip()
            if sql.upper().startswith("WHERE"):
                continue
            label = f"{md.parent.name}/{md.name}#{i}"
            yield label, sql, REMOTE_PREFIX in sql


def main():
    if shutil.which("duckdb") is None:
        print("SKIP: duckdb is not installed")
        return 0

    run_remote = os.environ.get("QUERY_CHECK_REMOTE", "1") != "0"
    blocks = list(sql_blocks())
    if not blocks:
        print("FAIL: no SQL blocks found; the docs lost their examples")
        return 1

    failures, skipped, ran = [], 0, 0
    for label, sql, is_remote in blocks:
        if is_remote and not run_remote:
            skipped += 1
            continue
        # Local queries use paths relative to the catalog directory.
        cwd = CATALOG
        try:
            proc = subprocess.run(
                ["duckdb", "-noheader", "-list", "-c", SETUP + sql],
                capture_output=True, text=True, cwd=cwd, timeout=TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            failures.append((label, f"timed out after {TIMEOUT}s"))
            continue
        ran += 1
        if proc.returncode != 0:
            first = (proc.stderr.strip().split("\n") or [""])[0]
            failures.append((label, first[:200]))

    for label, why in failures:
        print(f"FAIL {label}: {why}")

    tail = f", {skipped} remote skipped" if skipped else ""
    if failures:
        print(f"FAIL: {len(failures)}/{ran} documented queries failed{tail}")
        return 1

    print(f"PASS: {ran} documented queries run{tail}")
    if skipped:
        print("  Remote queries were skipped. Unset QUERY_CHECK_REMOTE to "
              "check the published URLs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
