"""Check that maintained documentation links survive a clean Git checkout.

Ignored author-local files must not satisfy a public documentation link. Include
new nonignored files while reviewing a change; CI checks the committed snapshot.
Historical paper/audit prose is deliberately outside this maintained guide set.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]


def check(root: Path = ROOT) -> list[str]:
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root,
    ).decode().split("\0")
    available = {name for name in listed if name and (root / name).is_file()}
    entrypoints = {
        "README.md", "CONTRIBUTING.md", "SECURITY.md",
        "fssai-ra/README.md", "fssai-ra/DEVELOPER_GUIDE.md",
        "fssai-ra/CONTRIBUTING.md", "fssai-ra/console/README.md",
    }
    sources = sorted(name for name in available if name.endswith(".md") and (
        name in entrypoints or name.startswith(("fssai-ra/docs/", "publications/"))
    ))
    errors = []
    for name in sources:
        source = root / name
        # Fenced examples can contain placeholder Markdown; they are not links.
        text = re.sub(r"```.*?```", "", source.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            local = unquote(target.split("#", 1)[0].strip("<>"))
            if not local:
                continue
            resolved = (source.parent / local).resolve()
            try:
                relative = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                errors.append(f"{name}: link leaves repository: {target}")
                continue
            directory = relative.rstrip("/") + "/"
            if relative not in available and not any(p.startswith(directory) for p in available):
                errors.append(f"{name}: unavailable in a clean checkout: {target}")
    print(f"Checked local file links in {len(sources)} maintained Markdown documents.")
    return errors


def main() -> int:
    errors = check()
    for error in errors:
        print(error)
    if not errors:
        print("Public documentation links resolve without ignored local archives.")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
