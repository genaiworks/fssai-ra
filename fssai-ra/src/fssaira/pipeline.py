"""Assembly: wire the five domains into one pipeline.

This is the convenience assembler used by demos, tests, and the adversarial
evaluation. It builds the diode, event log, snapshot store, transformer, tool
registry, evidence ledger, capability catalogue, policy enforcement point, and a
bounded agent.

The same seams accept the distributed adapters -- Kafka, Postgres, Redis,
Spark, Iceberg, a real model -- through :mod:`fssaira.plugins`, so the code an
institution runs in a pilot is the code exercised by the tests here.
"""
from __future__ import annotations

from .accountable_action import PolicyEnforcementPoint
from .bounded_intelligence import Agent, BoundedAgent, ToolRegistry, UntrustedEvidence
from .diode import OneWayChannel
from .event_transport import EventLog
from .evidence import EvidenceLedger
from .import_boundary import ImportBoundary, RawInput
from .metrics import Metrics
from .models.base import CapabilityCatalogue
from .reproducible_data import SnapshotStore, Transformer

# Tokens model separate write credentials held by services, never by agents.
EVIDENCE_TOKEN = "evidence-service-credential"



class FSSAIRAPipeline:
    def __init__(
        self,
        *,
        allow_egress: bool = False,
        approver=None,
        require_human_for_high_impact: bool = True,
        catalogue: CapabilityCatalogue | None = None,
        model=None,
        enforce_call_budget: bool = True,
    ) -> None:
        self.metrics = Metrics()
        self.evidence = EvidenceLedger(EVIDENCE_TOKEN)
        self.diode = OneWayChannel()
        self.events = EventLog()
        self.snapshots = SnapshotStore()
        self.transformer = Transformer()
        self.registry = ToolRegistry()
        self.catalogue = catalogue or CapabilityCatalogue.default()
        self._model = model

        # High side receives everything the diode delivers (append to the event log).
        self.diode.connect(lambda item: self.events.append(item, key=item.get("source", "")))

        self.import_boundary = ImportBoundary(
            self.diode, self.evidence, EVIDENCE_TOKEN, self.metrics,
            trusted_keys={}, allowed_types={"text/plain", "application/pdf"}, max_size=1_000_000,
        )
        self.pep = PolicyEnforcementPoint(
            self.evidence, EVIDENCE_TOKEN, self.metrics,
            allow_egress=allow_egress, approver=approver,
            require_human_for_high_impact=require_human_for_high_impact,
            catalogue=self.catalogue,
            enforce_call_budget=enforce_call_budget,
        )
        self._register_default_tools()

    #: Simulated side effects. Egress classification comes from the catalogue,
    #: so the tool registry and the model manifest can never disagree.
    EFFECTS = {
        "read_case": lambda **k: {"case": k.get("target"), "status": "read"},
        "prepare_recommendation": lambda **k: {"draft": "recommendation prepared"},
        "approve_award": lambda **k: {"award": "APPROVED"},
        "broaden_access": lambda **k: {"access": "widened"},
        "delete_evidence": lambda **k: {"evidence": "deleted"},
        "notify_external": lambda **k: {"sent": k.get("to")},
    }

    def _register_default_tools(self) -> None:
        for name, effect in self.EFFECTS.items():
            capability = self.catalogue.get(name)
            self.registry.register(
                name, effect, egress=bool(capability and capability.egress)
            )

    def trust_source(self, source: str, key: str) -> None:
        self.import_boundary.trust(source, key)

    def make_agent(
        self,
        agent_id: str,
        *,
        tools: set[str],
        operations: set[str] | None = None,
        data_scope: set[str] | None = None,
        model=None,
        max_calls: int = 8,
    ) -> BoundedAgent:
        """Build a least-privilege agent. Grants are explicit, never inferred."""
        agent = Agent(
            id=agent_id,
            allowed_tools=set(tools),
            permitted_operations=set(operations or tools),
            data_scope=set(data_scope or {"assigned_cases"}),
            tool_registry=self.registry,
            max_calls=max_calls,
        )
        backend = model or self._model
        if backend is None:
            from .models.deterministic import DeterministicModel

            backend = DeterministicModel(agent_id, catalogue=self.catalogue)
        return BoundedAgent(agent, backend, self.pep, self.evidence, EVIDENCE_TOKEN, self.metrics)

    def make_student_support_agent(self, agent_id: str = "student-support-1", *, model=None) -> BoundedAgent:
        return self.make_agent(
            agent_id,
            tools={"read_case", "prepare_recommendation"},
            operations={"read_case", "prepare_recommendation"},
            model=model,
        )

    def ingest_document(self, raw: RawInput) -> UntrustedEvidence:
        return self.import_boundary.ingest(raw)
