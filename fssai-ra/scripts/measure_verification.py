#!/usr/bin/env python3
"""Measure how fast the independent verifier recomputes an archived evidence chain.

    python scripts/measure_verification.py --records 200000 --out audit/verification-throughput.json

Builds an in-memory ledger of ``--records`` decisions, archives it into a SQLite
archive through ``archive_evidence``, then times a full recomputation and an
incremental pass over 100 new records. One run on one host: the figures size a
verification cadence, they do not promise one.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fssaira.evidence import EvidenceLedger  # noqa: E402
from fssaira.iceberg_backend import archive_evidence  # noqa: E402
from fssaira.small_data import SqliteArchiveStore, verify_archive  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--records", type=int, default=200_000)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    token = "measurement"
    ledger = EvidenceLedger(token)
    for index in range(args.records):
        ledger.append("decision", {"request_id": f"r-{index}", "case": "x" * 40}, token=token)
    with tempfile.TemporaryDirectory() as root:
        archive = SqliteArchiveStore(Path(root) / "archive.sqlite3")
        archive_evidence(ledger, archive)
        started = time.perf_counter()
        full = verify_archive(archive, mode="full")
        full_seconds = time.perf_counter() - started
        for index in range(args.records, args.records + 100):
            ledger.append("decision", {"request_id": f"r-{index}"}, token=token)
        archive_evidence(ledger, archive)
        started = time.perf_counter()
        incremental = verify_archive(archive, mode="incremental")
        incremental_seconds = time.perf_counter() - started
        archive.close()
    report = {
        "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": {"system": platform.system(), "machine": platform.machine(),
                 "cpus": os.cpu_count(), "python": platform.python_version()},
        "records": args.records,
        "full_pass": {"verdict": full["verdict"], "seconds": round(full_seconds, 3),
                      "records_per_second": round(args.records / full_seconds)},
        "incremental_pass": {"verdict": incremental["verdict"], "new_records": 100,
                             "seconds": round(incremental_seconds, 4)},
        "scope": "one run on one host; sizes a verification cadence, does not promise one",
    }
    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.out:
        args.out.write_text(rendered + "\n", encoding="utf-8")
    ok = full["verdict"] == incremental["verdict"] == "INTACT"
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
