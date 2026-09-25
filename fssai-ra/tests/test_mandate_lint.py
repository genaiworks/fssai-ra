"""A mandate broader than its purpose is refused before the task starts."""
import json
from pathlib import Path

import pytest

from fssaira.tbc import AuthorityDenied, TaskContract, TrustRuntime
from fssaira.tbc.mandate import CODES, lint_mandate, load_purposes
from test_tbc_sdk import AUTHORITIES, declarations

ROOT = Path(__file__).resolve().parents[1]
PURPOSES = load_purposes(ROOT / "profiles/tbc/purposes.json")
CORPUS = sorted((ROOT / "profiles/tbc/mandate-corpus").glob("*.json"))


def codes(contract, now=1000):
    return sorted({f.code for f in lint_mandate(contract, PURPOSES, now=now)})


@pytest.mark.parametrize("case", CORPUS, ids=lambda p: p.stem)
def test_every_corpus_mandate_yields_exactly_its_expected_findings(case):
    entry = json.loads(case.read_text())
    assert codes(TaskContract.parse(entry["contract"])) == sorted(entry["expect"]), entry["why"]


def test_the_corpus_covers_every_finding_the_lint_can_produce():
    covered = {code for case in CORPUS for code in json.loads(case.read_text())["expect"]}
    assert covered == set(CODES)
    assert any(not json.loads(case.read_text())["expect"] for case in CORPUS)  # a good mandate too


def test_the_shipped_example_contract_is_broader_than_its_purpose():
    """The lint's first run: the repository's own example over-grants a correction."""
    task = TaskContract.parse(json.loads((ROOT / "profiles/tbc/education-task.json").read_text()))
    findings = lint_mandate(task, PURPOSES, now=1000)
    assert [(f.code, f.detail.split()[0]) for f in findings] == [
        ("MANDATE_UNNEEDED_OPERATION", "receive_message"),
        ("MANDATE_UNNEEDED_OPERATION", "send_message"),
        ("MANDATE_UNNEEDED_OPERATION", "spawn_agent"),
        ("MANDATE_UNNEEDED_DESTINATION", "public"),
        ("MANDATE_OPEN_ENDED", "expires"),
    ]


def runtime(tmp_path, purposes):
    passport, _task, _identity = declarations()
    return TrustRuntime(tmp_path / "tbc.db", passport, authorities=AUTHORITIES, clock=lambda: 1000,
                        mandate_purposes=purposes)


def test_with_declared_purposes_an_over_broad_mandate_does_not_start(tmp_path):
    _passport, task, identity = declarations()
    r = runtime(tmp_path, PURPOSES)
    with pytest.raises(AuthorityDenied, match="MANDATE_UNNEEDED_OPERATION"):
        r.create_task("operator-key", task, identity_scope=identity, model="offline-scripted", zone="local")
    assert r.db.execute("SELECT count(*) FROM tbc_tasks").fetchone()[0] == 0
    good = TaskContract.parse(json.loads((ROOT / "profiles/tbc/mandate-corpus/"
                                          "good-minimal-correction.json").read_text())["contract"])
    assert r.create_task("operator-key", good, identity_scope=identity, model="offline-scripted",
                         zone="local")["agent"]
    r.close()


def test_without_declared_purposes_behaviour_is_unchanged(tmp_path):
    _passport, task, identity = declarations()
    r = runtime(tmp_path, None)
    assert r.create_task("operator-key", task, identity_scope=identity, model="offline-scripted",
                         zone="local")["agent"]
    r.close()


def test_a_purpose_profile_must_be_complete(tmp_path):
    path = tmp_path / "purposes.json"
    path.write_text(json.dumps({"correction": {"operations": []}}))
    with pytest.raises(ValueError, match="missing"):
        load_purposes(path)
