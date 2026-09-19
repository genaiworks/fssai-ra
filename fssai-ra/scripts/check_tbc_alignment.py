"""Validate the exact v11 source, executable claim bindings and SDK inventory.

This is a drift check, not a proof of semantic equivalence. Behavioral bindings
run separately under pytest. Updating the paper requires reviewing this manifest.
"""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from fssaira.tbc.contracts import PRIMITIVES, Passport  # noqa: E402
from fssaira.tbc.runtime import SCHEMAS  # noqa: E402


def resolve(locator, root=ROOT):
    path, symbol = locator.split(":")
    tree = ast.parse((root / path).read_text())
    for component in symbol.split("."):
        tree = next((node for node in tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
                     and node.name == component), None)
        if tree is None:
            raise ValueError(f"Missing executable binding: {locator}")


def check(root=ROOT):
    manifest = json.loads((root / "paper/tbc-v11/implementation.json").read_text())
    source = (root / manifest["source"]).read_bytes()
    if hashlib.sha256(source).hexdigest() != manifest["source_sha256"]:
        raise ValueError("Paper changed: review the implementation manifest before accepting new claims")
    with zipfile.ZipFile(root / manifest["source"]) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = ["".join(t.text or "" for t in p.findall(".//w:t", ns))
                  for p in document.findall(".//w:body/w:p", ns)]
    ids = set()
    for claim in manifest["claims"]:
        if claim["id"] in ids or not claim["scope"] or not claim["tests"]:
            raise ValueError("Incomplete or duplicate claim")
        ids.add(claim["id"])
        if not all(claim["paper_term"] in paragraphs[i] for i in claim["paragraphs"]):
            raise ValueError(f"Paper anchor drift: {claim['id']}")
        resolve(claim["implementation"], root)
        for test in claim["tests"]:
            resolve(test, root)
    figures = json.loads((root / "evaluation/results/v1.0.0-summary.json").read_text())["figures"]
    table_text = " ".join(t.text or "" for t in document.findall(".//w:tbl//w:t", ns))
    quoted = [
        f"{figures['arm_a_containment']:.0%} → {figures['arm_b_containment']:.0%} → {figures['arm_c_containment']:.0%}",
        f"{figures['domain_pack_scenarios_contained']}/{figures['domain_pack_scenarios_total']} hostile contained",
        f"{figures['domain_pack_benign_completed']}/{figures['domain_pack_benign_total']} benign completed",
        f"{figures['domain_pack_unauthorized_mutations']} unauthorised mutations",
        f"{figures['controls_load_bearing']}/{figures['controls_ablated']} tested controls",
        f"{figures['thesis_attempts_display']} bounded falsification attempts",
    ]
    if not all(phrase in table_text for phrase in quoted):
        raise ValueError("Word-paper figures differ from generated component results")
    passport = Passport.parse(json.loads((root / "profiles/tbc/education-passport.json").read_text()))
    if set(passport.inventory) != set(SCHEMAS) or set(SCHEMAS) != PRIMITIVES:
        raise ValueError("Passport, SDK and dispatch inventory disagree")
    return {"source_sha256": manifest["source_sha256"], "mechanisms_bound": len(ids),
            "primitives_bound": len(SCHEMAS), "metric_bindings": len(quoted), "passed": True}


if __name__ == "__main__":
    print(json.dumps(check(), indent=2))
