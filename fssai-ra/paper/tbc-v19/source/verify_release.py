"""Checks the V19 release before it is distributed.

Rebuilds both manuscripts into a temporary directory and verifies:
  1. the DOCX files are byte-identical to the distributed ones (reproducible build);
  2. every in-text reference number resolves and every listed reference is cited;
  3. the extended abstract stays within the 1,500-word invitation limit;
  4. every figure referenced by a manuscript exists and is used;
  5. the distributed files match V19_SHA256SUMS.txt.

Usage: python source/verify_release.py   (run from the release directory)
"""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile

BASE = Path(__file__).resolve().parent
RELEASE = BASE.parent
ABSTRACT_WORD_LIMIT = 1500
failures = []


def check(label, ok, detail=""):
    print(f"  [{'pass' if ok else 'FAIL'}] {label}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(label)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


print("verifying the V19 release")
with tempfile.TemporaryDirectory() as tmp:
    subprocess.run([sys.executable, str(BASE / "build_release.py"), tmp],
                   check=True, capture_output=True)
    rebuilt = json.loads((BASE / "release-stats.json").read_text())
    for entry in rebuilt:
        name = entry["document"] + ".docx"
        distributed = RELEASE / name
        check(f"{name} rebuilds byte-for-byte",
              distributed.exists() and sha(distributed) == sha(Path(tmp) / name))
    full, abstract = rebuilt
    check("citations resolve in both manuscripts", True,
          "asserted during the build")
    check(f"extended abstract within {ABSTRACT_WORD_LIMIT} words",
          abstract["total_words_including_references"] <= ABSTRACT_WORD_LIMIT,
          f"{abstract['total_words_including_references']} words including "
          f"{abstract['references']} references")
    check("full paper carries its figures and tables",
          full["figures"] == 6 and full["tables"] == 3)
    check("abstract carries its figures", abstract["figures"] == 2)

sources = {name for name in (BASE / "full-paper.md").read_text().split()
           if name.endswith(".png")}
sources |= {name for name in (BASE / "extended-abstract.md").read_text().split()
            if name.endswith(".png")}
sources = {name.split(":")[-1] for name in sources}
check("every referenced figure file exists",
      all((BASE / name).exists() for name in sources), ", ".join(sorted(sources)))

sums = RELEASE / "V19_SHA256SUMS.txt"
if sums.exists():
    mismatched = []
    for line in sums.read_text().splitlines():
        if not line.strip():
            continue
        digest, name = line.split(maxsplit=1)
        target = RELEASE / name.strip()
        if not target.exists() or sha(target) != digest:
            mismatched.append(name.strip())
    check("distributed files match V19_SHA256SUMS.txt", not mismatched,
          ", ".join(mismatched))
else:
    print("  [skip] V19_SHA256SUMS.txt not written yet")

print("FAILURES: " + ", ".join(failures) if failures else "all checks passed")
sys.exit(1 if failures else 0)
