"""FSSAI-RA: a Fail-Secure Sovereign AI Reference Architecture.

A vendor-neutral, runnable reference implementation of the five-domain
architecture: import boundary (diode), event transport (Kafka-like),
reproducible data (Spark/Iceberg-like), bounded intelligence (router + local
model + least-privilege agents), and accountable action (policy enforcement +
human approval + tamper-evident evidence).
"""
from __future__ import annotations

__version__ = "0.5.0"

from .accountable_action import ActionClass, Decision, PolicyEnforcementPoint, Tool, ToolCall
from .bounded_intelligence import (
    Agent, BoundedAgent, ModelBackend, RuleBasedLocalModel, ToolRegistry, UntrustedEvidence,
)
from .contract import ControlContract, Requirement
from .diode import DiodeBreachError, OneWayChannel
from .event_transport import Event, EventLog, KafkaLike
from .evidence import EvidenceError, EvidenceLedger, EvidenceRecord
from .exact_action import (
    AccountableExecutor, ActionProposal, Approval, ApprovalAuthority, ApprovalUseStore, CaseRegister,
    ExecutionDenied, ExecutionResult, ExecutionUncertain, PendingOutcome,
    PendingOutcomeStore, TEACHING_APPROVAL_KEY_ID,
)
from .import_boundary import ImportBoundary, QuarantineError, RawInput
from .metrics import Metrics
from .pipeline import FSSAIRAPipeline
from .reproducible_data import Snapshot, SnapshotStore, Transformer
from .profiles import ApplicationProfile, ProfileError, TransitionRule
from .evaluation import EvaluationReport, EvaluationRunner, ScenarioResult
from .control_plane import ControlPlane, MemoryObjectStore

__all__ = [
    "__version__",
    "ActionClass", "Decision", "PolicyEnforcementPoint", "Tool", "ToolCall",
    "Agent", "BoundedAgent", "ModelBackend", "RuleBasedLocalModel", "ToolRegistry", "UntrustedEvidence",
    "ControlContract", "Requirement",
    "DiodeBreachError", "OneWayChannel",
    "Event", "EventLog", "KafkaLike",
    "EvidenceError", "EvidenceLedger", "EvidenceRecord",
    "AccountableExecutor", "ActionProposal", "Approval", "ApprovalAuthority", "ApprovalUseStore", "CaseRegister",
    "ExecutionDenied", "ExecutionResult", "ExecutionUncertain", "PendingOutcome",
    "PendingOutcomeStore", "TEACHING_APPROVAL_KEY_ID",
    "ImportBoundary", "QuarantineError", "RawInput",
    "Metrics",
    "FSSAIRAPipeline",
    "Snapshot", "SnapshotStore", "Transformer",
    "ApplicationProfile", "ProfileError", "TransitionRule",
    "EvaluationReport", "EvaluationRunner", "ScenarioResult",
    "ControlPlane", "MemoryObjectStore",
]
