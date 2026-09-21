"""Check public file links and section anchors without ignored private archives."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[2]


def anchors(path: Path) -> set[str]:
    text = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.S)
    found = set(re.findall(r'''\b(?:id|name)=["']([^"']+)["']''', text))
    counts: dict[str, int] = {}
    if path.suffix == '.md':
        for heading in re.findall(r'^#{1,6}\s+(.+?)\s*#*$', text, flags=re.M):
            heading = re.sub(r'\[([^]]+)\]\([^)]*\)', r'\1', heading)
            heading = re.sub(r'<[^>]*>', '', heading)
            slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
            occurrence = counts.get(slug, 0)
            counts[slug] = occurrence + 1
            found.add(slug + (f'-{occurrence}' if occurrence else ''))
    return found


def check(root: Path = ROOT) -> list[str]:
    listed = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=root,
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
        text = re.sub(r"```.*?```", "", source.read_text(encoding="utf-8"), flags=re.S)
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", text):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target):
                continue
            local, _, fragment = target.strip('<>').partition('#')
            resolved = (source.parent / unquote(local)).resolve() if local else source.resolve()
            try:
                relative = resolved.relative_to(root.resolve()).as_posix()
            except ValueError:
                errors.append(f"{name}: link leaves repository: {target}")
                continue
            directory = relative.rstrip("/") + "/"
            if relative not in available and not any(p.startswith(directory) for p in available):
                errors.append(f"{name}: unavailable in a clean checkout: {target}")
            elif fragment and resolved.is_file() and resolved.suffix in {'.md', '.html'}:
                if unquote(fragment) not in anchors(resolved):
                    errors.append(f"{name}: missing section anchor: {target}")
    print(f"Checked file links and anchors in {len(sources)} maintained Markdown documents.")
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
