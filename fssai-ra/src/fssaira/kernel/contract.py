"""The seven-field control contract, enforced rather than described.

A capability contract names, for one consequential capability, the protected
asset, the permitted operation, the enforcement point outside the model, the
accountable owner, the failure test, the evidence artifact, and the failure
response. Two rules make it a build gate instead of a document:

* An empty or missing field is an *open governance decision*. It is returned to
  its owner, not engineered around, so loading fails.
* ``failure_test`` is a pytest node (``tests/test_x.py::test_name`` or
  ``tests/test_x.py::TestClass::test_name``) that pytest would actually run. The
  node must be defined in the parsed source of a file pytest collects
  (``test_*.py`` or ``*_test.py``). It must not be marked skip, skipif or xfail,
  or sit under ``__test__ = False``. A name that appears only as a substring, in a
  comment, or in a string does not exist.

The legacy requirement files (``contract/*.yaml``, keys ``owner`` and ``test``)
keep their prose tests and bind to executable checks through
``contract/bindings``. :func:`verify_bindings` holds those bindings to the same
existence standard. A ``CF-*`` conformance id exists only if a
``self._check(...)`` call registers it; a ``_skip`` does not count.
"""
from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

#: The seven fields, in the paper's order (Table 1).
FIELDS: tuple[str, ...] = (
    "protected_asset",
    "permitted_operation",
    "enforcement_point",
    "accountable_owner",
    "failure_test",
    "evidence_artifact",
    "failure_response",
)
_OPTIONAL = ("note", "rule")
_ALLOWED = frozenset(("id", *FIELDS, *_OPTIONAL))
_CONFORMANCE_ID = re.compile(r"^CF-[A-Z]+-\d+$")
_PYTEST_FILE = re.compile(r"^(test_.*|.*_test)\.py$")
_NOT_RUN_MARKS = ("skip", "xfail")


class ContractError(ValueError):
    """The contract cannot be relied on: a field is open or a named test is absent."""


@dataclass(frozen=True)
class CapabilityContract:
    """One consequential capability with all seven fields filled."""

    id: str
    domain: str
    protected_asset: str
    permitted_operation: str
    enforcement_point: str
    accountable_owner: str
    failure_test: str
    evidence_artifact: str
    failure_response: str
    failure_test_path: Path
    rule: str = ""
    note: str = ""


def _inside(root: Path, relative: str) -> Path:
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ContractError(f"locator {relative!r} is outside the repository")
    return path


def _node_index(source: str) -> dict[tuple[str, ...], ast.AST]:
    """Map each collectable definition path of a module to its AST node.

    Top-level functions and classes, and methods of (possibly nested) classes.
    Functions nested inside functions are not collectable nodes and are omitted.
    """
    tree = ast.parse(source)
    found: dict[tuple[str, ...], ast.AST] = {}

    def visit(body: list[ast.stmt], prefix: tuple[str, ...]) -> None:
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found[(*prefix, node.name)] = node
            elif isinstance(node, ast.ClassDef):
                found[(*prefix, node.name)] = node
                visit(node.body, (*prefix, node.name))

    visit(tree.body, ())
    found[()] = tree
    return found


def _defined_nodes(source: str) -> set[tuple[str, ...]]:
    return {path for path in _node_index(source) if path}


def _not_run_reason(node: ast.AST) -> str | None:
    """Why pytest would not run this node: a skip/xfail mark or ``__test__ = False``."""
    for decorator in getattr(node, "decorator_list", ()):
        text = ast.unparse(decorator)
        if any(mark in text for mark in _NOT_RUN_MARKS):
            return f"marked {text}"
    for statement in getattr(node, "body", ()):
        if (isinstance(statement, ast.Assign) and isinstance(statement.value, ast.Constant)
                and statement.value.value is False
                and any(isinstance(t, ast.Name) and t.id == "__test__" for t in statement.targets)):
            return "__test__ = False"
        if (isinstance(statement, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "pytestmark" for t in statement.targets)
                and any(mark in ast.unparse(statement.value) for mark in _NOT_RUN_MARKS)):
            return f"pytestmark = {ast.unparse(statement.value)}"
    return None


def resolve_test_locator(locator: str, *, root: Path, require_test: bool = True) -> Path:
    """Resolve ``path::name[::name]`` to its file, or raise :class:`ContractError`.

    With ``require_test`` the file must be one pytest collects, the final name a
    pytest test (``test_*``), any enclosing class a pytest class (``Test*``), and
    neither the node, its classes nor the module may be marked to skip or xfail.
    A parametrization suffix (``test_x[case]``) is accepted and ignored.
    """
    parts = [part.strip() for part in str(locator).split("::")]
    if len(parts) < 2 or not all(parts):
        raise ContractError(
            f"failure test {locator!r} must name a test node (path::test_name), not a whole file"
        )
    path = _inside(root, parts[0])
    names = tuple(parts[1:])
    names = (*names[:-1], names[-1].split("[", 1)[0])
    if require_test:
        if not _PYTEST_FILE.match(path.name):
            raise ContractError(f"{locator!r} is not a test: pytest does not collect {path.name!r}")
        if not names[-1].startswith("test"):
            raise ContractError(f"{locator!r} is not a test: {names[-1]!r} does not start with 'test'")
        for enclosing in names[:-1]:
            if not enclosing.startswith("Test"):
                raise ContractError(f"{locator!r} is not a test: class {enclosing!r} is not collected")
    if not path.is_file():
        raise ContractError(f"failure test {locator!r} does not exist: no file {parts[0]!r}")
    try:
        index = _node_index(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        raise ContractError(f"failure test {locator!r} does not exist: {parts[0]} does not parse ({exc})") from exc
    if names in index:
        if require_test:
            for depth in range(len(names) + 1):
                reason = _not_run_reason(index[names[:depth]])
                if reason:
                    raise ContractError(f"failure test {locator!r} would not run: {reason}")
        return path
    if not require_test and len(names) == 1:
        # Source locators may name a method without its class (``file::method``),
        # the convention the legacy bindings use. It resolves only when exactly
        # one definition carries that name; an ambiguous name resolves to nothing.
        matches = sorted(node for node in index if node and node[-1] == names[0])
        if len(matches) == 1:
            return path
        if len(matches) > 1:
            where = ", ".join("::".join(m) for m in matches)
            raise ContractError(f"locator {locator!r} is ambiguous in {parts[0]}: {where}")
    raise ContractError(f"failure test {locator!r} does not exist in {parts[0]}")


def _require_text(entry: dict, name: str, where: str) -> str:
    value = entry.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(
            f"{where}: field {name!r} is empty; this is an open governance decision, "
            "return it to its owner"
        )
    return value.strip()


def load_capability_contracts(directory: Path, *, root: Path) -> list[CapabilityContract]:
    """Load every ``*.yaml`` capability contract under ``directory``.

    Raises :class:`ContractError` on an empty or missing field, an unknown field,
    a duplicate id, or a failure test that does not exist or would not run.
    """
    directory = Path(directory)
    root = Path(root)
    contracts: list[CapabilityContract] = []
    seen: set[str] = set()
    files = sorted(directory.glob("*.yaml"))
    if not files:
        raise ContractError(f"no capability contracts found in {directory}")
    for path in files:
        try:
            doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ContractError(f"{path.name}: not valid YAML ({exc})") from exc
        if not isinstance(doc, dict):
            raise ContractError(f"{path.name}: a contract file must be a mapping")
        # The adjacent architecture inventory also has a ``capabilities`` mapping,
        # but it is a traceability catalogue rather than a seven-field executable
        # contract. A lifecycle capability contract declares its domain explicitly.
        if "domain" not in doc:
            continue
        domain = str(doc["domain"]).strip()
        entries = doc.get("capabilities")
        if not isinstance(entries, list) or not entries:
            raise ContractError(f"{path.name}: declares no capabilities")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                raise ContractError(f"{path.name}[{index}]: a capability must be a mapping")
            where = f"{path.name}:{entry.get('id') or index}"
            unknown = sorted(set(entry) - _ALLOWED)
            if unknown:
                raise ContractError(f"{where}: unknown field {unknown[0]!r}; the contract has exactly seven fields")
            capability_id = _require_text(entry, "id", where)
            if capability_id in seen:
                raise ContractError(f"{where}: duplicate capability id {capability_id!r}")
            seen.add(capability_id)
            values = {name: _require_text(entry, name, where) for name in FIELDS}
            test_path = resolve_test_locator(values["failure_test"], root=root)
            contracts.append(CapabilityContract(
                id=capability_id,
                domain=domain,
                failure_test_path=test_path,
                rule=str(entry.get("rule", "")).strip(),
                note=str(entry.get("note", "")).strip(),
                **values,
            ))
    return contracts


def _conformance_ids(root: Path) -> set[str]:
    """Ids registered by ``self._check("CF-...", ...)`` calls. A ``_skip`` is not a check."""
    path = root / "src" / "fssaira" / "conformance.py"
    if not path.is_file():
        return set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "_check"
                and node.args and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str) and _CONFORMANCE_ID.match(node.args[0].value)):
            ids.add(node.args[0].value)
    return ids


def _expand_conformance(locator: str) -> list[str]:
    ids: list[str] = []
    for piece in (p.strip() for p in locator.split(",")):
        if ".." in piece:
            start, end = (s.strip() for s in piece.split("..", 1))
            prefix_a, number_a = start.rsplit("-", 1)
            prefix_b, number_b = end.rsplit("-", 1)
            if prefix_a != prefix_b or int(number_b) < int(number_a):
                raise ContractError(f"malformed conformance range {piece!r}")
            width = len(number_a)
            ids.extend(f"{prefix_a}-{n:0{width}d}" for n in range(int(number_a), int(number_b) + 1))
        else:
            ids.append(piece)
    return ids


def _check_locator(locator: str, root: Path, conformance: set[str]) -> str | None:
    """Return a reason the locator does not resolve, or ``None`` if it does."""
    if locator.startswith("CF-"):
        try:
            ids = _expand_conformance(locator)
        except (ContractError, ValueError) as exc:
            return str(exc)
        missing = [cid for cid in ids if cid not in conformance]
        return f"conformance check(s) {', '.join(missing)} not defined" if missing else None
    path_part = locator.split("::", 1)[0]
    try:
        # Normalise first, so "./tests/x.py" is judged a test exactly as "tests/x.py" is.
        relative = _inside(root, path_part).relative_to(root.resolve()).as_posix()
    except ContractError as exc:
        return str(exc)
    is_test = relative.startswith("tests/")
    if "::" in locator:
        try:
            resolve_test_locator(relative + locator[len(path_part):], root=root, require_test=is_test)
        except ContractError as exc:
            return str(exc)
        return None
    path = root.resolve() / relative
    if not path.is_file():
        return f"file {locator!r} does not exist"
    if is_test:
        if not _PYTEST_FILE.match(path.name):
            return f"pytest does not collect {locator!r}"
        try:
            tests = {n for n in _defined_nodes(path.read_text(encoding="utf-8")) if n[-1].startswith("test")}
        except SyntaxError as exc:
            return f"test file {locator!r} does not parse ({exc})"
        if not tests:
            return f"test file {locator!r} defines no test"
    return None


def verify_bindings(contract_dir: Path, *, root: Path) -> list[str]:
    """Hold every legacy binding locator to the strict existence standard.

    Returns one finding per unresolved locator; an empty list means every
    executable binding names something that exists and would run.
    """
    from fssaira.coverage import load_bindings

    root = Path(root)
    conformance = _conformance_ids(root)
    findings: list[str] = []
    checked: set[tuple[str, str]] = set()
    for binding in load_bindings(str(contract_dir)):
        if binding.mechanism == "attestation":
            continue
        key = (binding.requirement_id, binding.locator)
        if key in checked:
            continue
        checked.add(key)
        reason = _check_locator(binding.locator, root, conformance)
        if reason:
            findings.append(f"{binding.requirement_id}: {binding.locator}: {reason}")
    return findings
