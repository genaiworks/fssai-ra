"""Every plane's must-NOT list is bound to tests that exist; every component imports."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from fssaira.kernel.contract import resolve_test_locator
from fssaira.planes import ALL_PLANES, Plane, PlaneError

ROOT = Path(__file__).resolve().parents[2]
CREDENTIAL_WORDS = ("token", "key", "credential", "secret", "signing", "custody")


def test_the_eight_responsibilities_of_figure_one():
    assert [p.name for p in ALL_PLANES] == [
        "boundary", "data", "intelligence", "authority",
        "execution", "context_gate", "evidence", "resilience",
    ]


def test_exactly_two_mediators_and_one_untrusted_plane():
    assert {p.name for p in ALL_PLANES if p.mediator} == {"execution", "context_gate"}
    assert {p.name for p in ALL_PLANES if p.untrusted} == {"intelligence"}
    assert not any(p.mediator and p.untrusted for p in ALL_PLANES)


@pytest.mark.parametrize("plane", ALL_PLANES, ids=lambda p: p.name)
def test_every_prohibition_is_bound_to_a_test_that_exists(plane):
    assert len(plane.must_not) >= 3
    for prohibition in plane.must_not:
        assert prohibition.text.strip()
        resolve_test_locator(prohibition.failure_test, root=ROOT)


@pytest.mark.parametrize("plane", ALL_PLANES, ids=lambda p: p.name)
def test_every_component_exists(plane):
    loaded = plane.load_components()
    assert len(loaded) == len(plane.components) >= 2


def test_a_missing_component_is_refused():
    ghost = Plane("ghost", "nothing", (), ("fssaira.evidence:NoSuchLedger",))
    with pytest.raises(PlaneError, match="does not exist"):
        ghost.load_components()


def test_a_live_agent_holds_no_copy_of_the_evidence_write_credential():
    """Signature checks miss a credential smuggled in any other way; inspect the object."""
    from fssaira.pipeline import EVIDENCE_TOKEN, FSSAIRAPipeline

    pipeline = FSSAIRAPipeline()
    bounded = pipeline.make_agent("audit-1", tools={"read_case"}, operations={"read_case"})
    for holder in (bounded, bounded.agent):
        for name, value in vars(holder).items():
            assert value != EVIDENCE_TOKEN, f"{type(holder).__name__}.{name} holds the credential"


def test_no_untrusted_component_is_constructed_with_a_credential():
    """The intelligence plane holds no key, token map or write credential."""
    [intelligence] = [p for p in ALL_PLANES if p.untrusted]
    for reference, component in intelligence.load_components().items():
        params = [name.lower() for name in inspect.signature(component).parameters]
        leaked = [name for name in params if any(word in name for word in CREDENTIAL_WORDS)]
        assert leaked == [], f"{reference} takes {leaked}"
