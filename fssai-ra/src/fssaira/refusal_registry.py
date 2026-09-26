"""The refusal-code registry, generated from the source that emits the codes.

Refusal codes are the architecture's public interface to auditors: a buyer's
conformance run searches for ``POLICY_VERSION_CHANGED`` or ``EPOCH_STALE``, not
for a stack trace. A registry written by hand drifts from the code the first
time someone adds a ``require``. This one is extracted from the syntax tree:

* the code argument of ``require(condition, "CODE")`` and of a local
  ``refuse("CODE", ...)`` / ``_refuse("CODE", ...)`` helper;
* the first argument of any exception whose class name ends in ``Denied``,
  ``Refused``, ``Exhausted``, ``Erased`` or ``Error`` when it is an upper-case
  code;
* string constants assigned in classes named ``...Code`` or ``...Codes``.

``docs/refusal_registry.json`` is the published copy; a test regenerates it and
fails on any difference, so a new code cannot ship unregistered.
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
CODE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
_EXCEPTION_SUFFIXES = ("Denied", "Refused", "Exhausted", "Erased", "Error")


def _name(func: ast.expr) -> str:
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _codes_in(tree: ast.AST) -> set[str]:
    found: set[str] = set()

    def take(node: ast.expr | None) -> None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and CODE.match(node.value):
            found.add(node.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = _name(node.func)
            if name == "require" and len(node.args) >= 2:
                take(node.args[1])
            elif name in ("refuse", "_refuse") and node.args or name.endswith(_EXCEPTION_SUFFIXES) and node.args:
                take(node.args[0])
        elif isinstance(node, ast.ClassDef) and node.name.endswith(("Code", "Codes")):
            for stmt in node.body:
                if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
                    take(stmt.value)
    return found


def scan(root: Path = PACKAGE) -> dict[str, list[str]]:
    """``{code: [module, ...]}`` for every refusal code the package can emit."""
    registry: dict[str, set[str]] = {}
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        module = ".".join(path.relative_to(root.parent).with_suffix("").parts)
        for code in _codes_in(ast.parse(path.read_text(encoding="utf-8"))):
            registry.setdefault(code, set()).add(module)
    return {code: sorted(modules) for code, modules in sorted(registry.items())}


def render(registry: dict[str, list[str]]) -> str:
    return json.dumps({"generated_by": "fssaira.refusal_registry", "count": len(registry),
                       "codes": registry}, indent=1, sort_keys=True) + "\n"


__all__ = ["render", "scan"]
