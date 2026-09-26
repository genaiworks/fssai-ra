"""One reproducible assurance report for the master guide's engineering claims.

An auditor should not have to run nine commands and trust nine printouts. This
module runs every engineering check the master guide cites, on this host, and
returns one JSON document whose ``digest`` is the SHA-256 of its canonical body.
Two parties running the same commit on equivalent hosts compare digests of the
``deterministic`` section; timing and host facts are kept apart in ``host``.

Sections:

* ``revocation`` -- the chaos campaign (design clean, ablations caught);
* ``adapter_qualification`` -- the reference SQLite store and sink driven
  through the campaign, and real threads racing revocation;
* ``evidence_federation`` -- a checkpoint published through forward-secure
  signing, time anchoring and a three-domain witness quorum, then verified,
  and a rewrite shown to fail;
* ``trusted_base`` -- SLOC per component, build measurement, SBOM summary;
* ``registry`` and ``specification_profile`` -- refusal codes and the swarm
  profile's cited tests;
* ``framework_catalogue`` -- every module, test and code the adoption
  framework's control catalogue cites exists.

A report says what the reference implementation does here. It is the input to
the deployment evidence bundle, not a substitute for it.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _revocation(seeds: int) -> dict:
    from .revocation_chaos import run_campaign

    campaign = run_campaign(seeds=seeds)
    return {"passed": campaign["design_holds"] and all(campaign["ablations_detected"].values()),
            "seeds": seeds,
            "arms": {name: {k: arm[k] for k in ("stale_effects", "duplicate_applications",
                                                "unreconciled", "refused_stale")}
                     for name, arm in campaign["arms"].items()}}


def _qualification(seeds: int, workdir: Path) -> dict:
    from .adapter_qualification import (
        SqlAuthorityStore,
        SqlSink,
        concurrent_revocation_check,
        qualify,
    )

    result = qualify(lambda seed, tasks: SqlAuthorityStore(workdir / f"s{seed}.db", tasks),
                     lambda seed: SqlSink(workdir / f"k{seed}.db"), seeds=seeds)
    store = SqlAuthorityStore(workdir / "race.db", tasks=3)
    try:
        race = concurrent_revocation_check(store, tasks=3, workers=6, commits_per_worker=40)
    finally:
        store.close()
    return {"passed": result["qualified"] and race["linearizable"],
            "chaos": {k: result[k] for k in ("code", "runs", "stale_effects",
                                             "duplicate_applications", "unreconciled")},
            "concurrency": {"code": race["code"], "violations": len(race["violations"])},
            "_host": {"commits": race["commits"], "revocations": race["revocations"]}}


def _federation(workdir: Path) -> dict:
    from .evidence_federation import (
        EvidenceFederation,
        fs_head_verifier,
        prove_record,
        verify_federated,
        verify_record,
    )
    from .forward_secure import ForwardSecureSigner
    from .time_anchor import TimeServer
    from .transparency import MerkleWitness, WitnessIdentity

    now = [1000.0]
    signer = ForwardSecureSigner(key_id="report-fs", start=0, period_seconds=3600, periods=4)
    verify = fs_head_verifier({"report-fs": signer.root_public})
    witnesses = [MerkleWitness(workdir / name, verify_head=verify, domain=name, key_id=name,
                               clock=lambda: now[0])
                 for name in ("regulator", "internal-audit", "civil-society")]
    servers = [TimeServer(f"time-{i}", radius=2.0, clock=lambda i=i: now[0] + 0.2 * i)
               for i in range(3)]
    federation = EvidenceFederation(signer=signer, time_servers=servers, witnesses=witnesses,
                                    clock=lambda: now[0])
    trust = {"fs_roots": {"report-fs": signer.root_public},
             "witnesses": {w.key_id: WitnessIdentity(w.public_key, w.domain) for w in witnesses},
             "time_keys": {k: v for s in servers for k, v in s.public_keys.items()}}
    leaves = [f"record-{i}".encode() for i in range(64)]
    federation.publish(leaves[:16])
    now[0] = 5000.0
    grown = federation.publish(leaves)
    valid = verify_federated(grown, threshold=3, leaves=leaves, **trust)
    included = verify_record(prove_record(leaves, 41), grown)
    now[0] = 6000.0
    rewrite = federation.publish([b"rewritten"] + leaves[1:])
    rewrite_check = verify_federated(rewrite, threshold=2, **trust)
    return {"passed": valid["valid"] and included["included"] and not rewrite_check["valid"],
            "grown_checkpoint": valid["code"], "distinct_domains": len(valid["distinct_domains"]),
            "inclusion": {"code": included["code"], "proof_hashes": included["proof_hashes"],
                          "tree_size": included["tree_size"]},
            "rewrite": {"code": rewrite_check["code"],
                        "witness_refusals": sorted({r["code"] for r in rewrite.refusals})}}


def _trusted_base() -> dict:
    from .trusted_base import build_measurement, measure_size, sbom

    size = measure_size()
    bom = sbom()
    return {"passed": size["trusted_fraction"] is not None and not size["native_code_in_package"],
            "components": {k: v["sloc"] for k, v in size["components"].items()},
            "trusted_sloc": size["trusted_sloc"], "package_sloc": size["package_sloc"],
            "build_measurement": build_measurement()["measurement"],
            "sbom": {"format": f"CycloneDX {bom['specVersion']}",
                     "components": len(bom["components"]), "serial": bom["serialNumber"]}}


def _registry() -> dict:
    from .refusal_registry import render, scan

    published = ROOT / "docs" / "refusal_registry.json"
    current = render(scan())
    return {"passed": published.exists() and published.read_text(encoding="utf-8") == current,
            "codes": len(scan())}


def _profile() -> dict:
    from .threats import locator_exists

    path = ROOT / "docs" / "SPECIFICATION_SWARM_PROFILE.md"
    if not path.exists():
        return {"passed": False, "requirements": 0, "missing": ["profile not found"]}
    rows = re.findall(r"^\|\s*(SW-[A-Z]-\d+)\s*\|[^\n]*?`(tests/[^`]+)`", path.read_text(), re.M)
    missing = [f"{rid}: {loc}" for rid, loc in rows if not locator_exists(ROOT, loc)]
    return {"passed": bool(rows) and not missing, "requirements": len(rows), "missing": missing}


def _framework() -> dict:
    from .framework import load, validate

    problems = validate()
    return {"passed": not problems, "controls": len(load().controls),
            "broken_references": len(problems)}


def build_report(*, seeds: int = 100, qualification_seeds: int = 20) -> dict:
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="fssaira-assure-") as tmp:
        work = Path(tmp)
        (work / "q").mkdir()
        (work / "f").mkdir()
        sections = {
            "revocation": _revocation(seeds),
            "adapter_qualification": _qualification(qualification_seeds, work / "q"),
            "evidence_federation": _federation(work / "f"),
            "trusted_base": _trusted_base(),
            "registry": _registry(),
            "specification_profile": _profile(),
            "framework_catalogue": _framework(),
        }
    host = {"python": platform.python_version(), "platform": platform.platform(),
            "seconds": round(time.perf_counter() - started, 2)}
    for section in sections.values():
        extra = section.pop("_host", None)
        if extra:
            host.update(extra)
    deterministic = {"sections": sections,
                     "passed": all(section["passed"] for section in sections.values())}
    body = json.dumps(deterministic, sort_keys=True, separators=(",", ":"))
    return {"verdict": "PASS" if deterministic["passed"] else "FAIL",
            "digest": hashlib.sha256(body.encode()).hexdigest(),
            "deterministic": deterministic, "host": host}


__all__ = ["build_report"]
