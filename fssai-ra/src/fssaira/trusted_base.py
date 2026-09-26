"""Measure the trusted base instead of asserting it is small.

"The model is untrusted; a small trusted enforcer decides" is only as strong as
the word *small*. A critic is right to ask how small, which files, which
dependencies, and how a buyer knows the enforcer running in production is the
one that was reviewed. This module answers with three artefacts, all
deterministic so two parties computing them get the same bytes:

* **size** -- source lines of code (SLOC: lines holding code, excluding blank
  lines, comments and docstrings) for each trusted component, and the fraction
  of the whole package that is trusted;
* **software bill of materials** (SBOM) -- the installed third-party packages
  the enforcer depends on, in CycloneDX 1.5 JSON, the format supply-chain
  scanners read;
* **build measurement** -- a SHA-256 of every trusted file and one digest over
  them all. A remote-attestation service (TPM, confidential-computing quote, or
  signed deployment manifest) pins this digest; a changed enforcer changes it.

The trusted-component list is the architectural claim. Everything not on it --
model adapters, evaluation, the CLI, the web API, storage back ends reached only
through a trusted interface -- may be wrong without breaking an authority or
disclosure rule, and the test suite is what holds that line.
"""
from __future__ import annotations

import ast
import hashlib
import io
import json
import platform
import re
import tokenize
import uuid
from importlib import metadata
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent

TRUSTED_COMPONENTS: dict[str, tuple[str, ...]] = {
    "kernel": ("kernel/*.py",),
    "decision plane": ("tbc/runtime.py", "tbc/contracts.py", "tbc/mandate.py",
                       "exact_action.py", "accountable_action.py", "delegation.py",
                       "grant_delegation.py", "disclosure.py", "disclosure_tokens.py",
                       "envelope_mac.py"),
    "evidence plane": ("evidence.py", "evidence_notary.py", "chain_verification.py",
                       "checkpoint_notary.py", "witness.py", "transparency.py",
                       "forward_secure.py", "time_anchor.py", "evidence_federation.py"),
    "key custody": ("key_custody.py", "custody_store.py", "kms_vault.py"),
    "containment": ("agent_cell.py", "isolation.py"),
}

_NON_CODE = {tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT,
             tokenize.DEDENT, tokenize.ENCODING, tokenize.ENDMARKER}


def sloc(source: str) -> int:
    """Lines carrying code: not blank, not comment-only, not docstring."""
    docstring_lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                end = body[0].end_lineno or body[0].lineno
                docstring_lines.update(range(body[0].lineno, end + 1))
    code_lines: set[int] = set()
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type not in _NON_CODE:
            code_lines.update(range(token.start[0], token.end[0] + 1))
    return len(code_lines - docstring_lines)


def _files(patterns: tuple[str, ...], root: Path) -> list[Path]:
    found: set[Path] = set()
    for pattern in patterns:
        matches = sorted(root.glob(pattern))
        if not matches:
            raise FileNotFoundError(f"trusted component file missing: {pattern}")
        found.update(matches)
    return sorted(found)


def trusted_files(root: Path = PACKAGE) -> dict[str, list[Path]]:
    return {name: _files(patterns, root) for name, patterns in TRUSTED_COMPONENTS.items()}


def measure_size(root: Path = PACKAGE) -> dict:
    components = {}
    trusted: set[Path] = set()
    for name, files in trusted_files(root).items():
        per_file = {str(f.relative_to(root)): sloc(f.read_text(encoding="utf-8")) for f in files}
        components[name] = {"files": len(files), "sloc": sum(per_file.values()),
                            "per_file": per_file}
        trusted.update(files)
    everything = [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]
    total = sum(sloc(p.read_text(encoding="utf-8")) for p in everything)
    trusted_sloc = sum(sloc(p.read_text(encoding="utf-8")) for p in trusted)
    native = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                    if p.suffix in {".so", ".pyd", ".dylib", ".c"} and "__pycache__" not in p.parts)
    return {"components": components, "trusted_sloc": trusted_sloc, "package_sloc": total,
            "trusted_fraction": round(trusted_sloc / total, 4) if total else None,
            "native_code_in_package": native,
            "language": "Python (memory-safe at the source level; CPython and native "
                        "dependencies are inherited trust, listed in the SBOM)"}


def build_measurement(root: Path = PACKAGE) -> dict:
    files = sorted({f for fs in trusted_files(root).values() for f in fs})
    digests = {str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
               for f in files}
    aggregate = hashlib.sha256(json.dumps(digests, sort_keys=True).encode()).hexdigest()
    return {"algorithm": "sha256", "files": digests, "measurement": aggregate,
            "python": platform.python_version()}


def _requirement_names(dist: str, extras: set[str]) -> list[str]:
    names = []
    for req in metadata.requires(dist) or []:
        marker = req.split(";", 1)[1] if ";" in req else ""
        extra = re.search(r"extra\s*==\s*['\"]([^'\"]+)['\"]", marker)
        if extra and extra.group(1) not in extras:
            continue
        names.append(re.split(r"[\s\[<>=!~;(]", req, maxsplit=1)[0])
    return names


def sbom(*, extras: tuple[str, ...] = ("privacy",), distribution: str = "fssai-ra") -> dict:
    """CycloneDX 1.5 SBOM of the enforcer's installed dependency closure."""
    try:
        version = metadata.version(distribution)
    except metadata.PackageNotFoundError:
        version = "unknown"
    seen: dict[str, str] = {}
    pending = (_requirement_names(distribution, set(extras))
               if version != "unknown" else ["pyyaml", "cryptography"])
    while pending:
        name = pending.pop()
        key = name.lower().replace("_", "-")
        if key in seen:
            continue
        try:
            seen[key] = metadata.version(name)
        except metadata.PackageNotFoundError:
            seen[key] = "not-installed"
            continue
        pending.extend(_requirement_names(name, set()))
    components = [{"type": "library", "name": n, "version": v,
                   "purl": f"pkg:pypi/{n}@{v}", "scope": "required"}
                  for n, v in sorted(seen.items())]
    body = {"bomFormat": "CycloneDX", "specVersion": "1.5", "version": 1,
            "metadata": {"component": {"type": "application", "name": distribution,
                                       "version": version,
                                       "purl": f"pkg:pypi/{distribution}@{version}"}},
            "components": components}
    serial = uuid.UUID(hashlib.sha256(json.dumps(body, sort_keys=True).encode())
                       .hexdigest()[:32])
    return {**body, "serialNumber": f"urn:uuid:{serial}"}


def report(root: Path = PACKAGE) -> dict:
    return {"size": measure_size(root), "build": build_measurement(root), "sbom": sbom()}


__all__ = ["TRUSTED_COMPONENTS", "build_measurement", "measure_size", "report", "sbom", "sloc",
           "trusted_files"]
