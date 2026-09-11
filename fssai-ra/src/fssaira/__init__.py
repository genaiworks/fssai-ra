"""FSSAI-RA: a Fail-Secure Sovereign AI Reference Architecture.

A vendor-neutral, runnable reference implementation of the five-domain
architecture for agentic AI that touches consequential decisions:

1. **Import boundary** — validated, signed, sanitised, one-way ingestion.
2. **Event transport** — durable, ordered, replayable (Kafka).
3. **Reproducible data** — lineage-logged transforms and versioned snapshots
   with rollback (Spark, Iceberg).
4. **Bounded intelligence** — a local model (Ollama by default) that proposes,
   with least-privilege agents and retrieved text treated strictly as data.
5. **Accountable action** — an executor that verifies the *actual* operation
   against current policy, an approval bound to one exact proposal, idempotent
   execution, and a tamper-evident record.

The central rule, and everything here exists to make it observable::

    A model may propose an action. It cannot manufacture the authority
    to execute it.

Three things make that rule checkable rather than aspirational:

* :mod:`fssaira.verification` — bounded model checking over a profile's whole
  declared authority space, not just the cases someone thought to test.
* :mod:`fssaira.evaluation` — adversarial containment *and* a benign-task
  utility baseline *and* ablations proving each control is load-bearing.
* :mod:`fssaira.conformance` — a portable suite an institution runs against its
  own backends, so replacing a component does not quietly void the argument.
"""
from __future__ import annotations

__version__ = "1.0.0"

from .accountable_action import (
    ActionClass, Decision, DenyCode, PolicyEnforcementPoint, Tool, ToolCall,
)
from .atomic_execution import AtomicExecutor
from .bounded_intelligence import (
    Agent, BoundedAgent, ModelBackend, Route, RuleBasedLocalModel, TaskRouter,
    ToolRegistry, UntrustedEvidence,
)
from .conformance import Bundle, ConformanceReport, run_conformance
from .contract import ControlContract, Requirement
from .control_plane import ControlPlane, MemoryObjectStore
from .diode import (
    DiodeBreachError, OneWayChannel, ReturnPathError, assert_no_return_path, describe_channel,
)
from .diode_transport import (
    Interface, InterfaceInventory, UdpDiodeReceiver, UdpDiodeSender,
)
from .evaluation import (
    AblationResult, CoverageSummary, EvaluationReport, EvaluationRunner,
    ScenarioResult, UtilityResult,
)
from .event_transport import Event, EventLog, KafkaLike
from .evidence import EvidenceError, EvidenceLedger, EvidenceRecord
from .exact_action import (
    AccountableExecutor, ActionProposal, Approval, ApprovalAuthority, ApprovalUseStore,
    CaseRegister, ExecutionDenied, ExecutionResult, ExecutionUncertain, PendingOutcome,
    PendingOutcomeStore, TEACHING_APPROVAL_KEY_ID,
)
from .import_boundary import ImportBoundary, IngestReport, QuarantineError, RawInput
from .metrics import Metrics
from .models import (
    Capability, CapabilityCatalogue, DeterministicModel, ModelSelection,
    OllamaModel, OpenAICompatibleModel, build_model, select_model,
)
from .pipeline import FSSAIRAPipeline
from .plugins import PluginError, PluginInfo, available, create, register
from .profiles import ApplicationProfile, ProfileError, TransitionRule
from .reproducible_data import Snapshot, SnapshotStore, Transformer
from .security import AuthConfig, Authenticator, Principal
from .verification import ProfileVerifier, VerificationReport, verify_profile

__all__ = [
    "__version__",
    # accountable action
    "ActionClass", "Decision", "DenyCode", "PolicyEnforcementPoint", "Tool", "ToolCall",
    "AccountableExecutor", "AtomicExecutor", "ActionProposal", "Approval", "ApprovalAuthority",
    "ApprovalUseStore", "CaseRegister", "ExecutionDenied", "ExecutionResult",
    "ExecutionUncertain", "PendingOutcome", "PendingOutcomeStore", "TEACHING_APPROVAL_KEY_ID",
    # bounded intelligence
    "Agent", "BoundedAgent", "ModelBackend", "Route", "RuleBasedLocalModel", "TaskRouter",
    "ToolRegistry", "UntrustedEvidence", "Capability", "CapabilityCatalogue",
    "DeterministicModel", "ModelSelection", "OllamaModel", "OpenAICompatibleModel",
    "build_model", "select_model",
    # import boundary and diode
    "DiodeBreachError", "OneWayChannel", "ReturnPathError", "assert_no_return_path",
    "describe_channel", "Interface", "InterfaceInventory", "UdpDiodeReceiver", "UdpDiodeSender",
    "ImportBoundary", "IngestReport", "QuarantineError", "RawInput",
    # transport and data
    "Event", "EventLog", "KafkaLike", "Snapshot", "SnapshotStore", "Transformer",
    # evidence
    "EvidenceError", "EvidenceLedger", "EvidenceRecord",
    # governance and assurance
    "ControlContract", "Requirement", "ApplicationProfile", "ProfileError", "TransitionRule",
    "AblationResult", "CoverageSummary", "EvaluationReport", "EvaluationRunner",
    "ScenarioResult", "UtilityResult",
    "ProfileVerifier", "VerificationReport", "verify_profile",
    "Bundle", "ConformanceReport", "run_conformance",
    # platform
    "ControlPlane", "MemoryObjectStore", "FSSAIRAPipeline", "Metrics",
    "AuthConfig", "Authenticator", "Principal",
    "PluginError", "PluginInfo", "available", "create", "register",
]
