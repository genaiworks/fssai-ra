"""Measure the deployment isolation the architecture assumes, and gate on it.

Every authority control in this repository rests on one unstated assumption:
that the model runtime cannot reach the control plane except through mediation.
Until now that assumption was prose. A reader could run the whole suite green on
a laptop where the agent process shared a uid with the control database, could
open the cloud metadata service, and held standing credentials in its
environment -- exactly the conditions that turned a conventional flaw into
cross-cluster reach in the July 2026 disclosure.

This module does not *create* isolation. It **measures** it and refuses to call
an unmeasured host isolated. Each requirement is probed against the live host by
an explicit method; the outcome is one of three values, and ``not_measurable``
is never counted as success:

``satisfied``       the probe ran and observed the required property
``violated``        the probe ran and observed the property absent
``not_measurable``  the probe could not run here (wrong platform, no declared
                    target); the requirement stays open

A host qualifies as ``production`` only when every *required* requirement is
``satisfied``, the measurement is fresh, and it names an accountable operator
and a host identity. Anything else qualifies as ``reference`` -- the honest
status of a laptop, a CI runner, and this repository's own test environment.
``IsolationGate`` turns that verdict into a refusal at the point where a
deployment would otherwise promote itself.

The probes are injectable, so the test suite can present both an isolated and a
hostile host deterministically without needing either.
"""
from __future__ import annotations

import json
import os
import platform
import socket
import stat
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

SATISFIED = "satisfied"
VIOLATED = "violated"
NOT_MEASURABLE = "not_measurable"
OUTCOMES = (SATISFIED, VIOLATED, NOT_MEASURABLE)

#: Link-local addresses that expose instance credentials on the major clouds.
#: Reachability from a model-runtime process is the precondition that turned
#: code execution into cross-cluster authority in the public disclosure.
METADATA_ENDPOINTS = (
    ("169.254.169.254", 80),
    ("169.254.170.2", 80),
    ("fd00:ec2::254", 80),
)

#: Environment names whose presence in the *agent* environment means the agent
#: holds authority that mediation never issued.
CREDENTIAL_MARKERS = (
    "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_ACCESS_KEY_ID",
    "GOOGLE_APPLICATION_CREDENTIALS", "GCE_METADATA_HOST",
    "AZURE_CLIENT_SECRET", "AZURE_TENANT_ID",
    "KUBERNETES_SERVICE_HOST", "KUBERNETES_SERVICE_PORT",
    "GITHUB_TOKEN", "GH_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN",
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY",
    "DATABASE_URL", "POSTGRES_PASSWORD", "REDIS_PASSWORD",
)

#: The in-pod service account token path. Present and readable means the agent
#: can authenticate to the cluster API without passing any declared control.
SERVICE_ACCOUNT_TOKEN = "/var/run/secrets/kubernetes.io/serviceaccount/token"


class IsolationNotQualified(RuntimeError):
    """A deployment asked for production authority without measured isolation."""


@dataclass(frozen=True)
class Requirement:
    id: str
    title: str
    rationale: str
    required: bool = True


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "control_store_not_writable",
        "The agent identity cannot write the control database",
        "Every durable authority decision -- stop flags, quarantine, epochs, evidence -- "
        "lives in the control store. If the model runtime can write it, no control in "
        "this architecture holds, because the record of the decision is the decision.",
    ),
    Requirement(
        "distinct_runtime_identity",
        "The agent runs under a different OS identity than the control service",
        "Shared-uid deployments give the agent the control service's file authority "
        "regardless of what the mediation layer decides.",
    ),
    Requirement(
        "code_immutable_to_agent",
        "The agent cannot modify the enforcement code it is mediated by",
        "A writable enforcement package converts any code-execution flaw into a "
        "permanent, silent removal of every control.",
    ),
    Requirement(
        "no_ambient_cloud_metadata",
        "The instance metadata service is unreachable from the agent",
        "Metadata reachability yields instance credentials that no task contract "
        "issued and no envelope can attenuate.",
    ),
    Requirement(
        "no_service_account_token",
        "No in-pod service-account token is readable by the agent",
        "A readable projected token authenticates the agent to the cluster API "
        "directly, outside all declared mediation.",
    ),
    Requirement(
        "egress_default_deny",
        "Undeclared outbound network destinations are refused by the host",
        "Destination authorisation in software is a contract, not a boundary. "
        "Without host-level default-deny, an agent reaches any address it names.",
    ),
    Requirement(
        "no_standing_credentials",
        "The agent environment carries no standing credential material",
        "Standing credentials are the amplifier: they survive task expiry, ignore "
        "scope attenuation, and are not revoked when a workload is stopped.",
    ),
    Requirement(
        "kernel_sandbox_active",
        "A kernel-enforced sandbox confines the agent process",
        "seccomp, Landlock or an equivalent confines the blast radius of code "
        "execution to the syscalls the workload declared.",
        required=False,
    ),
)

REQUIREMENTS_BY_ID = {r.id: r for r in REQUIREMENTS}


@dataclass(frozen=True)
class Measurement:
    requirement: str
    outcome: str
    method: str
    detail: str = ""

    def __post_init__(self) -> None:
        if self.requirement not in REQUIREMENTS_BY_ID:
            raise ValueError(f"unknown isolation requirement: {self.requirement}")
        if self.outcome not in OUTCOMES:
            raise ValueError(f"invalid outcome: {self.outcome}")

    def to_dict(self) -> dict:
        return {
            "requirement": self.requirement,
            "title": REQUIREMENTS_BY_ID[self.requirement].title,
            "required": REQUIREMENTS_BY_ID[self.requirement].required,
            "outcome": self.outcome,
            "method": self.method,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class HostAttribution:
    """Who measured, where, and when. Unattributed evidence never qualifies."""

    operator: str
    host_id: str
    measured_at: float

    def __post_init__(self) -> None:
        for name in ("operator", "host_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip() or len(value) > 200:
                raise ValueError(f"isolation evidence requires a named {name}")
        if not isinstance(self.measured_at, (int, float)) or self.measured_at <= 0:
            raise ValueError("isolation evidence requires a measurement time")

    def to_dict(self) -> dict:
        return {"operator": self.operator, "host_id": self.host_id,
                "measured_at": self.measured_at}


@dataclass(frozen=True)
class IsolationReport:
    attribution: HostAttribution
    measurements: tuple[Measurement, ...]
    platform: str
    #: Evidence older than this is not accepted for production qualification.
    max_age_seconds: int = 86_400

    def by_id(self, requirement: str) -> Measurement | None:
        for measurement in self.measurements:
            if measurement.requirement == requirement:
                return measurement
        return None

    @property
    def unmeasured(self) -> tuple[str, ...]:
        seen = {m.requirement for m in self.measurements}
        return tuple(r.id for r in REQUIREMENTS if r.required and r.id not in seen)

    @property
    def violations(self) -> tuple[Measurement, ...]:
        return tuple(m for m in self.measurements
                     if REQUIREMENTS_BY_ID[m.requirement].required and m.outcome == VIOLATED)

    @property
    def open_requirements(self) -> tuple[Measurement, ...]:
        return tuple(m for m in self.measurements
                     if REQUIREMENTS_BY_ID[m.requirement].required
                     and m.outcome == NOT_MEASURABLE)

    def stale(self, now: float) -> bool:
        return (now - self.attribution.measured_at) > self.max_age_seconds

    def qualification(self, now: float | None = None) -> str:
        """``production`` only on complete, fresh, satisfied, attributed evidence."""
        now = time.time() if now is None else now
        if self.stale(now) or self.unmeasured or self.violations or self.open_requirements:
            return "reference"
        return "production"

    def blocking_reasons(self, now: float | None = None) -> tuple[str, ...]:
        now = time.time() if now is None else now
        reasons: list[str] = []
        if self.stale(now):
            age = int(now - self.attribution.measured_at)
            reasons.append(f"evidence is {age}s old; limit is {self.max_age_seconds}s")
        reasons.extend(f"{r}: never measured" for r in self.unmeasured)
        reasons.extend(f"{m.requirement}: violated ({m.detail})" for m in self.violations)
        reasons.extend(f"{m.requirement}: not measurable here ({m.detail})"
                       for m in self.open_requirements)
        return tuple(reasons)

    def to_dict(self, now: float | None = None) -> dict:
        now = time.time() if now is None else now
        return {
            "schema_version": "1.0",
            "kind": "isolation",
            "platform": self.platform,
            "attribution": self.attribution.to_dict(),
            "qualification": self.qualification(now),
            "blocking_reasons": list(self.blocking_reasons(now)),
            "summary": {
                "required_total": sum(1 for r in REQUIREMENTS if r.required),
                "satisfied": sum(1 for m in self.measurements if m.outcome == SATISFIED),
                "violated": sum(1 for m in self.measurements if m.outcome == VIOLATED),
                "not_measurable": sum(1 for m in self.measurements
                                      if m.outcome == NOT_MEASURABLE),
            },
            "measurements": [m.to_dict() for m in self.measurements],
            "limits": [
                "a passing measurement describes this host at this moment, not a "
                "continuous guarantee",
                "reachability probes establish absence of a path from this process, "
                "not the absence of every path",
                "no probe here replaces an adversarial exercise in the target "
                "deployment",
            ],
        }

    def write_json(self, path: str | Path, now: float | None = None) -> None:
        Path(path).write_text(json.dumps(self.to_dict(now), indent=2) + "\n")

    def render(self) -> str:
        glyph = {SATISFIED: "ok  ", VIOLATED: "FAIL", NOT_MEASURABLE: "open"}
        lines = [f"isolation: {self.qualification()}  ({self.platform})"]
        for measurement in self.measurements:
            requirement = REQUIREMENTS_BY_ID[measurement.requirement]
            mark = "" if requirement.required else " (advisory)"
            lines.append(f"  [{glyph[measurement.outcome]}] {measurement.requirement}{mark}"
                         f" -- {measurement.detail or measurement.method}")
        for reason in self.blocking_reasons():
            lines.append(f"  blocked: {reason}")
        return "\n".join(lines)


@dataclass
class HostProbe:
    """Measure the requirements against a host.

    Every external interaction is injectable so the suite can exercise both an
    isolated and a hostile host without provisioning either. The defaults are
    the real system calls; ``probe_host`` below runs them for real.
    """

    control_store: Path | None = None
    enforcement_root: Path | None = None
    agent_environ: Mapping[str, str] = field(default_factory=lambda: dict(os.environ))
    #: An address the deployment declares must NOT be reachable. Without one,
    #: egress default-deny is not measurable -- it is not assumed.
    egress_canary: tuple[str, int] | None = None
    connect: Callable[[tuple[str, int], float], None] | None = None
    getuid: Callable[[], int] = os.getuid
    agent_uid: int | None = None
    path_exists: Callable[[str], bool] = os.path.exists
    path_readable: Callable[[str], bool] = lambda p: os.access(p, os.R_OK)
    seccomp_status: Callable[[], str | None] | None = None
    timeout: float = 0.35

    def _connect(self, address: tuple[str, int]) -> None:
        if self.connect is not None:
            self.connect(address, self.timeout)
            return
        with socket.create_connection(address, timeout=self.timeout):
            pass

    # -- individual probes -------------------------------------------------

    def control_store_not_writable(self) -> Measurement:
        rid = "control_store_not_writable"
        if self.control_store is None:
            return Measurement(rid, NOT_MEASURABLE, "declared-path",
                               "no control store path declared")
        target = Path(self.control_store)
        if not target.exists():
            return Measurement(rid, NOT_MEASURABLE, "stat",
                               f"{target} does not exist")
        if self.agent_uid is None or self.agent_uid == self.getuid():
            return Measurement(
                rid, VIOLATED, "stat",
                "the measuring process is the agent identity, so the store is "
                "writable by the agent by construction")
        mode = target.stat().st_mode
        owner = target.stat().st_uid
        world_or_group_writable = bool(mode & (stat.S_IWGRP | stat.S_IWOTH))
        if owner == self.agent_uid or world_or_group_writable:
            return Measurement(rid, VIOLATED, "stat",
                               f"mode {stat.filemode(mode)} uid {owner} is writable "
                               f"by agent uid {self.agent_uid}")
        return Measurement(rid, SATISFIED, "stat",
                           f"mode {stat.filemode(mode)} owned by uid {owner}")

    def distinct_runtime_identity(self) -> Measurement:
        rid = "distinct_runtime_identity"
        if self.agent_uid is None:
            return Measurement(rid, NOT_MEASURABLE, "getuid",
                               "no agent uid declared for this deployment")
        service_uid = self.getuid()
        if self.agent_uid == service_uid:
            return Measurement(rid, VIOLATED, "getuid",
                               f"agent and control service share uid {service_uid}")
        return Measurement(rid, SATISFIED, "getuid",
                           f"control uid {service_uid}, agent uid {self.agent_uid}")

    def code_immutable_to_agent(self) -> Measurement:
        rid = "code_immutable_to_agent"
        root = Path(self.enforcement_root) if self.enforcement_root else Path(__file__).parent
        if not root.exists():
            return Measurement(rid, NOT_MEASURABLE, "stat", f"{root} does not exist")
        if self.agent_uid is None or self.agent_uid == self.getuid():
            return Measurement(
                rid, VIOLATED, "stat",
                "the measuring process is the agent identity and can write the "
                "enforcement package")
        mode = root.stat().st_mode
        if mode & (stat.S_IWGRP | stat.S_IWOTH) or root.stat().st_uid == self.agent_uid:
            return Measurement(rid, VIOLATED, "stat",
                               f"enforcement package mode {stat.filemode(mode)}")
        return Measurement(rid, SATISFIED, "stat",
                           f"enforcement package mode {stat.filemode(mode)}")

    def no_ambient_cloud_metadata(self) -> Measurement:
        rid = "no_ambient_cloud_metadata"
        reached = []
        for address in METADATA_ENDPOINTS:
            try:
                self._connect(address)
            except OSError:
                continue
            reached.append(f"{address[0]}:{address[1]}")
        if reached:
            return Measurement(rid, VIOLATED, "tcp-connect",
                               "metadata service reachable: " + ", ".join(reached))
        return Measurement(rid, SATISFIED, "tcp-connect",
                           f"no connection to {len(METADATA_ENDPOINTS)} known endpoints")

    def no_service_account_token(self) -> Measurement:
        rid = "no_service_account_token"
        if not self.path_exists(SERVICE_ACCOUNT_TOKEN):
            return Measurement(rid, SATISFIED, "stat", "no projected token present")
        if self.path_readable(SERVICE_ACCOUNT_TOKEN):
            return Measurement(rid, VIOLATED, "access",
                               f"{SERVICE_ACCOUNT_TOKEN} is readable")
        return Measurement(rid, SATISFIED, "access",
                           "projected token present but not readable")

    def egress_default_deny(self) -> Measurement:
        rid = "egress_default_deny"
        if self.egress_canary is None:
            return Measurement(
                rid, NOT_MEASURABLE, "tcp-connect",
                "no egress canary declared; default-deny is never assumed")
        try:
            self._connect(self.egress_canary)
        except OSError as error:
            return Measurement(rid, SATISFIED, "tcp-connect",
                               f"canary {self.egress_canary[0]} refused: "
                               f"{type(error).__name__}")
        return Measurement(rid, VIOLATED, "tcp-connect",
                           f"undeclared destination {self.egress_canary[0]} reachable")

    def no_standing_credentials(self) -> Measurement:
        rid = "no_standing_credentials"
        found = sorted(name for name in CREDENTIAL_MARKERS if self.agent_environ.get(name))
        if found:
            return Measurement(rid, VIOLATED, "environ",
                               "standing credential variables present: "
                               + ", ".join(found))
        return Measurement(rid, SATISFIED, "environ",
                           f"none of {len(CREDENTIAL_MARKERS)} credential variables set")

    def kernel_sandbox_active(self) -> Measurement:
        rid = "kernel_sandbox_active"
        if self.seccomp_status is not None:
            status = self.seccomp_status()
        elif platform.system() != "Linux":
            return Measurement(rid, NOT_MEASURABLE, "proc-status",
                               f"{platform.system()} exposes no seccomp mode here")
        else:
            status = None
            try:
                for line in Path("/proc/self/status").read_text().splitlines():
                    if line.startswith("Seccomp:"):
                        status = line.split(":", 1)[1].strip()
                        break
            except OSError as error:
                return Measurement(rid, NOT_MEASURABLE, "proc-status", str(error))
        if status is None:
            return Measurement(rid, NOT_MEASURABLE, "proc-status",
                               "no Seccomp field reported")
        if status in ("1", "2"):
            mode = {"1": "strict", "2": "filter"}[status]
            return Measurement(rid, SATISFIED, "proc-status", f"seccomp {mode} mode")
        return Measurement(rid, VIOLATED, "proc-status", "seccomp disabled")

    # -- composition -------------------------------------------------------

    def measure(self) -> tuple[Measurement, ...]:
        return tuple(getattr(self, requirement.id)() for requirement in REQUIREMENTS)


def probe_host(
    *,
    operator: str,
    host_id: str | None = None,
    control_store: str | Path | None = None,
    enforcement_root: str | Path | None = None,
    agent_uid: int | None = None,
    egress_canary: tuple[str, int] | None = None,
    agent_environ: Mapping[str, str] | None = None,
    now: float | None = None,
    probe: HostProbe | None = None,
) -> IsolationReport:
    """Measure this host and return an attributed, gate-ready report."""
    probe = probe or HostProbe(
        control_store=Path(control_store) if control_store else None,
        enforcement_root=Path(enforcement_root) if enforcement_root else None,
        agent_uid=agent_uid,
        egress_canary=egress_canary,
        agent_environ=dict(agent_environ) if agent_environ is not None else dict(os.environ),
    )
    attribution = HostAttribution(
        operator=operator,
        host_id=host_id or platform.node() or "unnamed-host",
        measured_at=time.time() if now is None else now,
    )
    return IsolationReport(
        attribution=attribution,
        measurements=probe.measure(),
        platform=f"{platform.system()} {platform.release()}",
    )


@dataclass(frozen=True)
class IsolationGate:
    """Refuse production authority without measured isolation.

    ``strict`` is the deployment setting. ``strict=False`` is the teaching
    setting and still returns the honest qualification, so a reference run can
    never print ``production``.
    """

    strict: bool = True

    def check(self, report: IsolationReport, *, now: float | None = None) -> str:
        qualification = report.qualification(now)
        if qualification != "production" and self.strict:
            reasons = "; ".join(report.blocking_reasons(now)) or "no measurements"
            raise IsolationNotQualified(
                "deployment is not isolation-qualified: " + reasons)
        return qualification


__all__ = [
    "CREDENTIAL_MARKERS", "METADATA_ENDPOINTS", "NOT_MEASURABLE", "OUTCOMES",
    "REQUIREMENTS", "REQUIREMENTS_BY_ID", "SATISFIED", "SERVICE_ACCOUNT_TOKEN",
    "VIOLATED", "HostAttribution", "HostProbe", "IsolationGate",
    "IsolationNotQualified", "IsolationReport", "Measurement", "Requirement",
    "probe_host",
]
