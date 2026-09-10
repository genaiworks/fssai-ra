"""Assembly: wire the five domains into one pipeline.

This is a convenience assembler for demos and tests. It builds the diode,
event log, snapshot store, transformer, tool registry, evidence ledger, policy
enforcement point, and a bounded agent, and exposes ``ingest_document`` and an
agent runner. Real deployments would wire the same seams to Kafka, Spark,
Iceberg, and a local model via the adapters.
"""
from __future__ import annotations

from .accountable_action import PolicyEnforcementPoint
from .bounded_intelligence import Agent, BoundedAgent, RuleBasedLocalModel, ToolRegistry
from .diode import OneWayChannel
from .event_transport import EventLog
from .evidence import EvidenceLedger
from .import_boundary import ImportBoundary, RawInput
from .metrics import Metrics
from .reproducible_data import SnapshotStore, Transformer

# Tokens model separate write credentials held by services, never by agents.
EVIDENCE_TOKEN = "evidence-service-credential"


class FSSAIRAPipeline:
    def __init__(self, *, allow_egress: bool = False, approver=None,
                 require_human_for_high_impact: bool = True) -> None:
        self.metrics = Metrics()
        self.evidence = EvidenceLedger(EVIDENCE_TOKEN)
        self.diode = OneWayChannel()
        self.events = EventLog()
        self.snapshots = SnapshotStore()
        self.transformer = Transformer()
        self.registry = ToolRegistry()

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
        )
        self._register_default_tools()

    def _register_default_tools(self) -> None:
        self.registry.register("read_case", lambda **k: {"case": k.get("target"), "status": "read"})
        self.registry.register("prepare_recommendation", lambda **k: {"draft": "recommendation prepared"})
        self.registry.register("approve_award", lambda **k: {"award": "APPROVED"})
        self.registry.register("broaden_access", lambda **k: {"access": "widened"})
        self.registry.register("delete_evidence", lambda **k: {"evidence": "deleted"})
        self.registry.register("notify_external", lambda **k: {"sent": k.get("to")}, egress=True)

    def trust_source(self, source: str, key: str) -> None:
        self.import_boundary._keys[source] = key

    def make_student_support_agent(self, agent_id: str = "student-support-1") -> BoundedAgent:
        agent = Agent(
            id=agent_id,
            allowed_tools={"read_case", "prepare_recommendation"},
            permitted_operations={"read_case", "prepare_recommendation"},
            data_scope={"assigned_cases"},
            tool_registry=self.registry,
        )
        model = RuleBasedLocalModel(agent_id)
        return BoundedAgent(agent, model, self.pep, self.evidence, EVIDENCE_TOKEN, self.metrics)

    def ingest_document(self, raw: RawInput):
        return self.import_boundary.ingest(raw)
