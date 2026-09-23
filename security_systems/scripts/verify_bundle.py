"""Verify SHA-256 file integrity of an extracted conference source bundle.

Run: python scripts/verify_bundle.py /path/to/extracted/security_systems
"""
import hashlib
import json
import sys
from pathlib import Path


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]).resolve()
    manifest = json.loads((root / "MANIFEST.sha256.json").read_text())
    failures = []
    for name, digest in manifest.items():
        path = (root / name).resolve()
        if root not in path.parents or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            failures.append(name)
    if failures:
        print("Integrity failed: " + ", ".join(failures))
        return 1
    print(f"Verified {len(manifest)} files. Integrity does not establish authorship or security.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
