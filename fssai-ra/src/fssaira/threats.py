"""An alignment-independent threat catalogue whose claims are checked to run.

The architecture's safety case is designed not to depend on the model being
aligned. That is a strong sentence, so it is held to the same rule as every
other claim here: each catalogued failure, whether a misaligned model gaming
its objective, an injected instruction, or a compromised signer, names the
control that stands in its way and the executable test that shows it, or it
says plainly that nothing here addresses it.

Three statuses keep the argument honest. ``contained`` means the governed harm
cannot occur through a governed interface in the tested fixtures whatever the
model intends. ``bounded`` means it is limited, deferred, or made detectable.
``residual`` means it remains, and the entry must say what remains. A catalogue
with no residuals would be a marketing document, so one is required.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

FAMILIES = ("alignment", "security", "data", "systemic")
STATUSES = ("contained", "bounded", "residual")


class ThreatCatalogueError(ValueError):
    """The catalogue is malformed or makes a claim nothing supports."""


@dataclass(frozen=True)
class Threat:
    id: str
    family: str
    title: str
    threat: str
    references: tuple[str, ...]
    controls: tuple[str, ...]
    status: str
    evidence: tuple[str, ...] = ()
    residual: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "family": self.family, "title": self.title,
            "threat": self.threat, "references": list(self.references),
            "controls": list(self.controls), "status": self.status,
            "evidence": list(self.evidence), "residual": self.residual,
        }


@dataclass
class ThreatReport:
    threats: tuple[Threat, ...]
    missing_locators: tuple[str, ...] = field(default_factory=tuple)

    def count(self, status: str, family: str | None = None) -> int:
        return sum(1 for t in self.threats
                   if t.status == status and (family is None or t.family == family))

    @property
    def holds(self) -> bool:
        return not self.missing_locators

    def to_dict(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "threat-catalogue",
            "summary": {
                "threats": len(self.threats),
                **{status: self.count(status) for status in STATUSES},
                "by_family": {
                    family: {status: self.count(status, family) for status in STATUSES}
                    for family in FAMILIES
                },
                "missing_locators": len(self.missing_locators),
                "holds": self.holds,
            },
            "missing_locators": list(self.missing_locators),
            "threats": [t.to_dict() for t in self.threats],
            "reading": [
                "contained means the governed harm did not occur through a governed interface "
                "in tested fixtures, whatever the model intended; it is not a probability",
                "bounded means the harm is limited, deferred, or detectable, not prevented",
                "residual entries are the research agenda, stated rather than omitted",
            ],
        }


def _strings(value, where: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise ThreatCatalogueError(f"{where} must be a list of non-empty strings")
    return tuple(v.strip() for v in value)


def load_catalogue(path: str | Path) -> tuple[Threat, ...]:
    source = Path(path)
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise ThreatCatalogueError(f"cannot load {source}: {exc}") from exc
    items = raw.get("threats")
    if not isinstance(items, list) or not items:
        raise ThreatCatalogueError("catalogue must contain a non-empty threats list")
    threats: list[Threat] = []
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ThreatCatalogueError(f"threat {index} must be a mapping")
        for key in ("id", "family", "title", "threat", "status"):
            if not isinstance(item.get(key), str) or not item[key].strip():
                raise ThreatCatalogueError(f"threat {index} {key} must be a non-empty string")
        tid = item["id"].strip()
        if tid in seen:
            raise ThreatCatalogueError(f"duplicate threat id {tid}")
        seen.add(tid)
        if item["family"] not in FAMILIES:
            raise ThreatCatalogueError(f"{tid} family must be one of {', '.join(FAMILIES)}")
        if item["status"] not in STATUSES:
            raise ThreatCatalogueError(f"{tid} status must be one of {', '.join(STATUSES)}")
        evidence = _strings(item.get("evidence"), f"{tid} evidence")
        controls = _strings(item.get("controls"), f"{tid} controls")
        residual = str(item.get("residual") or "").strip()
        if item["status"] in ("contained", "bounded") and not evidence:
            raise ThreatCatalogueError(
                f"{tid} claims {item['status']} with no evidence; a containment claim "
                "with nothing that runs behind it is not a claim"
            )
        if item["status"] in ("bounded", "residual") and not residual:
            raise ThreatCatalogueError(f"{tid} is {item['status']} but does not say what remains")
        if not controls:
            raise ThreatCatalogueError(f"{tid} must name the control considered")
        threats.append(Threat(
            id=tid, family=item["family"], title=item["title"].strip(),
            threat=item["threat"].strip(),
            references=_strings(item.get("references"), f"{tid} references"),
            controls=controls, status=item["status"], evidence=evidence, residual=residual,
        ))
    if not any(t.status == "residual" for t in threats):
        raise ThreatCatalogueError(
            "a catalogue with no residual threats is a marketing document; name what remains"
        )
    return tuple(threats)


def locator_exists(root: Path, locator: str) -> bool:
    """``path::function`` must name a file under root that defines that function."""
    path, _, name = locator.partition("::")
    target = root / path
    if not target.is_file():
        return False
    if not name:
        return True
    return re.search(rf"^\s*def {re.escape(name)}\(", target.read_text(encoding="utf-8"),
                     re.MULTILINE) is not None


def check_catalogue(path: str | Path, root: str | Path | None = None) -> ThreatReport:
    source = Path(path)
    base = Path(root) if root is not None else source.resolve().parent.parent
    threats = load_catalogue(source)
    missing = tuple(
        f"{t.id}: {locator}" for t in threats for locator in t.evidence
        if not locator_exists(base, locator)
    )
    return ThreatReport(threats=threats, missing_locators=missing)


__all__ = ["FAMILIES", "STATUSES", "Threat", "ThreatCatalogueError", "ThreatReport",
           "check_catalogue", "load_catalogue", "locator_exists"]
