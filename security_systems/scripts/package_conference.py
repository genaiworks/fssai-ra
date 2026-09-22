"""Build a source release with an integrity manifest; never publishes it."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {"__pycache__", ".pytest_cache", ".ruff_cache", ".venv", "build", "dist", ".DS_Store"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    files = {}
    for path in sorted(ROOT.rglob("*")):
        parts = path.relative_to(ROOT).parts
        if (path.is_file() and not path.is_symlink() and path.resolve() != args.out.resolve()
                and path.name != "MANIFEST.sha256.json"
                and not any(p in EXCLUDED or p.endswith(".egg-info") for p in parts)):
            files[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    manifest = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in files.items():
            archive.writestr("security_systems/" + name, data)
        archive.writestr("security_systems/MANIFEST.sha256.json", json.dumps(manifest, indent=2) + "\n")
    print(f"Packaged {len(files)} files: {args.out}")


if __name__ == "__main__":
    main()
