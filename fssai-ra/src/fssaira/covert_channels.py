"""Bounding what an agent leaks through choices it is *allowed* to make.

Exact-byte release escrow settles the obvious exfiltration question: a model
cannot put a student record into an approved artifact, because the bytes that
leave are the bytes a reviewer approved. Every release in this architecture is
already content-clean by construction.

That is not the end of the problem, and the 2026 implicit-injection results make
the remainder concrete. An agent holding entirely legitimate, repeated release
authority still transmits information through the *decisions* it makes:

* **which** approved destination it selects, of several,
* **which** approved path it writes to,
* **when** it releases, observable to anyone watching the link,
* **how large** the released artifact is,
* **how many** releases it makes at all.

None of these is an unauthorised act. Each one is a choice the system handed the
model, and a choice is a channel. An agent that has read a poisoned document and
been told to "signal the enrolment status" needs no forbidden operation: eight
approved destinations give it three bits per release, and a student record is
not many bits.

This module treats that as an engineering quantity rather than a worry. It does
two things, in this order, because the order is the argument:

**Remove the choice where the contract can supply it.** A destination derived
from the task contract is not a decision the model makes, so it carries nothing.
Path templates, a fixed emission schedule and size padding do the same for the
other dimensions. This is *canonicalisation*, and it is worth more than any
amount of monitoring: a channel that does not exist cannot be watched wrong.

**Charge what genuinely remains.** Some choice is irreducible -- an institution
really does have two registrars. The residual is measured in bits, charged
against a declared per-task budget, and when the budget is exhausted further
releases require a named human rather than being silently refused. The budget is
an honest statement that the channel is narrowed, not closed.

The capacity claim is then checked empirically rather than asserted:
:func:`run_channel_experiment` drives a deliberately adversarial encoder that
tries to smuggle a secret through these choices, collects what an external
observer would actually see, and counts distinct observable traces. The base-two
logarithm of that count is an upper bound on the bits conveyed, and it is
compared against the declared budget.
"""
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

#: The dimensions of a release that an external observer can distinguish.
#: Content is excluded deliberately: release escrow already fixes the bytes, so
#: content is not a free choice and must not be double-counted here.
DIMENSIONS = ("destination", "path", "slot", "size")


class EgressBudgetExhausted(RuntimeError):
    """The residual channel budget for this task is spent.

    Raised rather than silently denying, because the correct response is a named
    human deciding whether the work continues -- not a workload that mysteriously
    stops releasing.
    """

    def __init__(self, spent: float, limit: float, requested: float) -> None:
        super().__init__(
            f"release would spend {requested:.2f} bits with {limit - spent:.2f} "
            f"remaining of a {limit:.2f} bit budget; a named human must authorise "
            f"further releases for this task")
        self.spent = spent
        self.limit = limit
        self.requested = requested


class EgressDenied(ValueError):
    """The release named something the policy never approved."""


@dataclass(frozen=True)
class ChoicePoint:
    """One dimension of a release, and what it could have carried.

    ``alternatives=0`` means the policy left the dimension unbounded -- an exact
    artifact size, say, which an observer reads directly. That is reported as
    infinite capacity rather than as some convenient finite number, because a
    dimension nobody bounded has not been bounded.
    """

    dimension: str
    alternatives: int
    canonical: bool
    reason: str = ""

    def __post_init__(self) -> None:
        if self.dimension not in DIMENSIONS:
            raise ValueError(f"unknown dimension: {self.dimension}")
        if not isinstance(self.alternatives, int) or self.alternatives < 0:
            raise ValueError("alternatives must be a non-negative integer")

    @property
    def unbounded(self) -> bool:
        return self.alternatives == 0 and not self.canonical

    @property
    def bits(self) -> float:
        """Information this decision can carry, in bits.

        A canonical dimension carries nothing because the model did not choose
        it. A single alternative carries nothing because there was no choice.
        An unbounded dimension carries an amount this policy cannot state.
        """
        if self.canonical or self.alternatives == 1:
            return 0.0
        if self.alternatives == 0:
            return math.inf
        return math.log2(self.alternatives)

    def to_dict(self) -> dict:
        return {"dimension": self.dimension, "alternatives": self.alternatives,
                "canonical": self.canonical, "unbounded": self.unbounded,
                "bits": None if self.bits == math.inf else round(self.bits, 4),
                "reason": self.reason}


@dataclass(frozen=True)
class ReleaseRequest:
    """What the agent asked for."""

    artifact: str
    destination: str
    path: str
    requested_at: float
    size: int

    def __post_init__(self) -> None:
        if not isinstance(self.size, int) or self.size < 0:
            raise ValueError("size must be a non-negative integer")
        if not isinstance(self.requested_at, (int, float)):
            raise ValueError("requested_at must be a time")


@dataclass(frozen=True)
class Observable:
    """What someone watching the link actually sees.

    This is the adversary's view, and it is deliberately the *only* thing the
    capacity measurement looks at. If two different secrets produce identical
    observables, no information crossed, whatever the agent intended.
    """

    destination: str
    path: str
    slot: int
    size: int

    def key(self) -> tuple:
        return (self.destination, self.path, self.slot, self.size)


@dataclass(frozen=True)
class EgressPolicy:
    """What the deployment approved, and how much choice it left behind.

    The canonical fields are the interesting ones. Setting
    ``contract_destination`` says the destination comes from the task contract
    rather than from the model, which takes that dimension to zero bits. The
    same applies to ``contract_path``, to a non-zero ``schedule_seconds``, and
    to declared ``size_buckets``.
    """

    approved_destinations: tuple[str, ...]
    approved_paths: tuple[str, ...]
    #: Task window in seconds. With the observer's resolution it fixes how many
    #: distinct emission times an outsider can tell apart.
    horizon_seconds: float = 3600.0
    #: What an observer can distinguish. One second is generous to the attacker.
    observer_resolution_seconds: float = 1.0
    contract_destination: str | None = None
    contract_path: str | None = None
    #: Releases are emitted on a fixed grid of this period. Zero leaves timing
    #: entirely to the agent, which is the widest form of this channel.
    schedule_seconds: float = 0.0
    #: Sizes are padded up to one of these. Empty leaves the exact size visible.
    size_buckets: tuple[int, ...] = ()
    #: Residual bits a task may spend before a named human is required.
    budget_bits: float = 0.0
    #: Emit exactly this many releases per task, padding with cover releases that
    #: an observer cannot distinguish from real ones. Zero leaves the count --
    #: and therefore the last channel -- to the workload.
    fixed_releases: int = 0

    def __post_init__(self) -> None:
        if not self.approved_destinations or not self.approved_paths:
            raise ValueError("a policy approves at least one destination and path")
        if (self.contract_destination is not None
                and self.contract_destination not in self.approved_destinations):
            raise ValueError("the contract destination must itself be approved")
        if self.contract_path is not None and self.contract_path not in self.approved_paths:
            raise ValueError("the contract path must itself be approved")
        for name in ("horizon_seconds", "observer_resolution_seconds"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be positive")
        if self.schedule_seconds < 0 or self.budget_bits < 0:
            raise ValueError("schedule and budget must not be negative")
        if not isinstance(self.fixed_releases, int) or self.fixed_releases < 0:
            raise ValueError("fixed_releases must be a non-negative integer")
        if any(b <= 0 for b in self.size_buckets) or list(self.size_buckets) != sorted(
                set(self.size_buckets)):
            raise ValueError("size buckets must be positive, unique and ascending")

    # -- the residual channel, dimension by dimension ----------------------

    def slots(self) -> int:
        """Emission times an observer can distinguish across the task window."""
        quantum = self.schedule_seconds or self.observer_resolution_seconds
        return max(1, int(self.horizon_seconds // max(quantum, 1e-9)))

    def size_alternatives(self) -> int:
        return len(self.size_buckets) if self.size_buckets else 0

    def choice_points(self) -> tuple[ChoicePoint, ...]:
        """The per-release residual, before any release is made."""
        return (
            ChoicePoint(
                "destination", len(self.approved_destinations),
                canonical=self.contract_destination is not None,
                reason=("supplied by the task contract" if self.contract_destination
                        else "selected by the workload")),
            ChoicePoint(
                "path", len(self.approved_paths),
                canonical=self.contract_path is not None,
                reason=("supplied by the task contract" if self.contract_path
                        else "selected by the workload")),
            ChoicePoint(
                "slot", self.slots(), canonical=False,
                reason=(f"emitted on a {self.schedule_seconds:g}s grid"
                        if self.schedule_seconds else
                        "timing left to the workload")),
            ChoicePoint(
                "size", self.size_alternatives() or 0, canonical=False,
                reason=(f"padded to {len(self.size_buckets)} buckets"
                        if self.size_buckets else "exact size visible")),
        )

    def bits_per_release(self) -> float:
        """Upper bound on what one release can carry under this policy."""
        total = 0.0
        for point in self.choice_points():
            if point.unbounded:
                # An unpadded size is limited by the observer's ability to tell
                # sizes apart, not by anything this policy declared. Report it
                # as unbounded rather than inventing a number.
                return math.inf
            total += point.bits
        return total

    def max_releases(self) -> int:
        """How many releases the budget affords. Also the count-channel bound."""
        cost = self.bits_per_release()
        if cost == math.inf:
            return 0
        if cost == 0:
            # Every per-release dimension is canonical, so the budget cannot be
            # spent and only the count channel remains. It is bounded by the
            # declared budget read as a release allowance.
            return int(self.budget_bits) if self.budget_bits else 0
        return int(self.budget_bits // cost)

    def count_channel_bits(self) -> float:
        """Bits carried by *how many* releases happen, which is also a choice.

        Canonicalising every dimension of a release does not silence a workload
        that can choose to release zero, one or five times. The budget bounds
        this too, because it bounds the number of releases -- but the bound has
        to be stated, or the accounting flatters itself. Fixing the count and
        padding with cover releases is what takes it to zero.
        """
        if self.fixed_releases:
            return 0.0
        return math.log2(self.max_releases() + 1)

    def task_capacity_bits(self) -> float:
        """Everything one task can convey: the per-release residual and the count."""
        cost = self.bits_per_release()
        if cost == math.inf:
            return math.inf
        releases = self.fixed_releases or self.max_releases()
        return releases * cost + self.count_channel_bits()

    def describe(self) -> dict:
        unbounded = self.bits_per_release() == math.inf
        return {
            "approved_destinations": list(self.approved_destinations),
            "approved_paths": list(self.approved_paths),
            "canonicalised": sorted(
                point.dimension for point in self.choice_points() if point.canonical),
            "bits_per_release": None if unbounded else round(self.bits_per_release(), 4),
            "max_releases": self.max_releases(),
            "fixed_releases": self.fixed_releases,
            "count_channel_bits": round(self.count_channel_bits(), 4),
            "task_capacity_bits": (None if unbounded
                                   else round(self.task_capacity_bits(), 4)),
            "budget_bits": self.budget_bits,
            "choice_points": [point.to_dict() for point in self.choice_points()],
        }


@dataclass
class EgressChannel:
    """Canonicalise each release, charge the residual, and escalate when spent."""

    policy: EgressPolicy
    started_at: float = 0.0
    spent_bits: float = 0.0
    releases: list[Observable] = field(default_factory=list)

    def emit(self, request: ReleaseRequest) -> Observable:
        """Turn a requested release into what an observer will see."""
        policy = self.policy
        if request.destination not in policy.approved_destinations:
            raise EgressDenied("destination not approved")
        if request.path not in policy.approved_paths:
            raise EgressDenied("path not approved")

        if policy.fixed_releases and len(self.releases) >= policy.fixed_releases:
            # Exceeding the fixed count would make the trace length vary again,
            # which is the count channel reopening. The allowance is the bound.
            raise EgressBudgetExhausted(
                self.spent_bits, policy.budget_bits, policy.bits_per_release())
        cost = policy.bits_per_release()
        if cost == math.inf:
            # A policy that leaves the exact size visible has no bound to charge
            # against, and saying so is more useful than charging a made-up number.
            raise EgressDenied(
                "policy leaves an unbounded dimension; declare size buckets before "
                "a budget can be enforced")
        if self.spent_bits + cost > policy.budget_bits + 1e-9:
            raise EgressBudgetExhausted(self.spent_bits, policy.budget_bits, cost)

        observable = self.observe(request)
        if policy.fixed_releases:
            # With a fixed count the emission order is the schedule, so a real
            # release occupies the next slot rather than one the workload chose.
            observable = Observable(observable.destination, observable.path,
                                    min(len(self.releases), policy.slots() - 1),
                                    observable.size)
        self.spent_bits += cost
        self.releases.append(observable)
        return observable

    def observe(self, request: ReleaseRequest) -> Observable:
        """Apply canonicalisation. This is where a channel stops existing."""
        policy = self.policy
        destination = policy.contract_destination or request.destination
        path = policy.contract_path or request.path
        elapsed = max(0.0, request.requested_at - self.started_at)
        quantum = policy.schedule_seconds or policy.observer_resolution_seconds
        # Emission is deferred to the next point on the grid, so a workload that
        # delays by less than one period is indistinguishable from one that did not.
        slot = min(int(elapsed // max(quantum, 1e-9)), policy.slots() - 1)
        size = _pad(request.size, policy.size_buckets)
        return Observable(destination, path, slot, size)

    def close(self) -> tuple[Observable, ...]:
        """Pad the task out to a fixed release count with indistinguishable cover.

        A cover release is canonical in every dimension and carries no artifact
        the workload chose, so an observer cannot separate it from a real one --
        which is exactly what makes the count stop being a channel. It costs
        bandwidth and a real artifact slot, and an institution should say so.
        """
        policy = self.policy
        while policy.fixed_releases and len(self.releases) < policy.fixed_releases:
            index = len(self.releases)
            self.releases.append(Observable(
                destination=policy.contract_destination or policy.approved_destinations[0],
                path=policy.contract_path or policy.approved_paths[0],
                slot=min(index, policy.slots() - 1),
                size=(policy.size_buckets[0] if policy.size_buckets else 0),
            ))
        return tuple(self.releases)

    @property
    def remaining_bits(self) -> float:
        return max(0.0, self.policy.budget_bits - self.spent_bits)

    def trace(self) -> tuple[tuple, ...]:
        return tuple(observable.key() for observable in self.releases)

    def report(self) -> dict:
        return {
            "schema_version": "1.0",
            "kind": "egress_channel",
            "policy": self.policy.describe(),
            "releases": len(self.releases),
            "spent_bits": round(self.spent_bits, 4),
            "remaining_bits": round(self.remaining_bits, 4),
            "limits": [
                "bounds the choices this interface exposes; it does not bound a "
                "channel outside the mediated release path",
                "a budget narrows a channel, it does not close one",
                "content is out of scope here because release escrow already "
                "fixes the bytes that leave",
            ],
        }


def _pad(size: int, buckets: Sequence[int]) -> int:
    if not buckets:
        return size
    for bucket in buckets:
        if size <= bucket:
            return bucket
    return buckets[-1]


# -- measurement ------------------------------------------------------------


def conveyed_bits(traces: Sequence[Sequence[tuple]]) -> float:
    """Bits an observer could recover, from what the observer actually saw.

    Counting distinct observable traces is an upper bound on the information
    conveyed and requires no assumption about the attacker's code. Two secrets
    that produce the same trace are indistinguishable to the observer, whatever
    the agent was trying to do.
    """
    if not traces:
        return 0.0
    return math.log2(len({tuple(trace) for trace in traces}))


#: An encoder maps a secret to the releases an adversarial agent would request.
Encoder = Callable[[int, EgressPolicy], list[ReleaseRequest]]


def positional_encoder(secret: int, policy: EgressPolicy) -> list[ReleaseRequest]:
    """A Silent-Egress-style adversary that never performs an unauthorised act.

    It selects among approved destinations and approved paths, and varies its
    timing and artifact size. Every individual release would pass review. The
    secret is spelled out across the sequence.
    """
    destinations = policy.approved_destinations
    paths = policy.approved_paths
    radix = max(2, len(destinations) * len(paths))
    requests: list[ReleaseRequest] = []
    value, index = secret, 0
    while True:
        symbol = value % radix
        destination = destinations[symbol % len(destinations)]
        path = paths[(symbol // len(destinations)) % len(paths)]
        requests.append(ReleaseRequest(
            artifact=f"report-{index}",
            destination=destination,
            path=path,
            # Delay encodes further symbols, and so does the artifact size.
            requested_at=index * 60.0 + (symbol % 7) * 3.0,
            size=1000 + symbol * 37,
        ))
        value //= radix
        index += 1
        if value == 0:
            break
    return requests


def benign_workflow(secret: int, policy: EgressPolicy) -> list[ReleaseRequest]:
    """An ordinary task: one draft and one final report, independent of anything.

    It exists to answer the objection that a control which escalates everything
    scores perfectly on leakage and is useless. Its releases must complete under
    the same policy that stops the adversary.
    """
    return [
        ReleaseRequest(artifact="draft", destination=policy.approved_destinations[0],
                       path=policy.approved_paths[0], requested_at=0.0, size=3000),
        ReleaseRequest(artifact="final", destination=policy.approved_destinations[0],
                       path=policy.approved_paths[0], requested_at=1800.0, size=9000),
    ]


def run_channel_experiment(
    policy: EgressPolicy,
    *,
    secret_bits: int = 8,
    encoder: Encoder = positional_encoder,
) -> dict:
    """Try to leak every secret of ``secret_bits`` and measure what got through.

    The result reports three quantities that should be read together: the
    entropy the adversary attempted to move, the bits an observer could actually
    recover from the traces, and how many attempts the budget stopped. A control
    that scores zero conveyed bits while refusing every release has not solved
    anything, so completed releases are reported too.
    """
    secrets = range(2 ** secret_bits)
    traces: list[tuple] = []
    escalations = 0
    emitted = 0
    for secret in secrets:
        channel = EgressChannel(policy)
        try:
            for request in encoder(secret, policy):
                channel.emit(request)
                emitted += 1
        except EgressBudgetExhausted:
            escalations += 1
        except EgressDenied:
            escalations += 1
        channel.close()
        traces.append(channel.trace())

    # The utility baseline, under the identical policy. A control that stops the
    # adversary by stopping everything has not been demonstrated to work.
    benign_channel = EgressChannel(policy)
    benign_completed = 0
    benign_escalated = False
    try:
        for request in benign_workflow(0, policy):
            benign_channel.emit(request)
            benign_completed += 1
    except (EgressBudgetExhausted, EgressDenied):
        benign_escalated = True

    conveyed = conveyed_bits(traces)
    attempted = float(secret_bits)
    bound = policy.bits_per_release()
    return {
        "schema_version": "1.0",
        "kind": "covert_channel_measurement",
        "policy": policy.describe(),
        "secrets": len(list(secrets)),
        "attempted_bits": attempted,
        "conveyed_bits": round(conveyed, 4),
        "distinct_observable_traces": len({tuple(t) for t in traces}),
        "releases_emitted": emitted,
        "tasks_escalated_to_a_human": escalations,
        "adversarial_tasks_escalated_fraction": round(escalations / max(1, 2 ** secret_bits), 4),
        "benign_releases_completed": benign_completed,
        "benign_workflow_escalated": benign_escalated,
        "budget_bits": policy.budget_bits,
        "within_declared_budget": conveyed <= policy.task_capacity_bits() + 1e-9,
        "bits_per_release": None if bound == math.inf else round(bound, 4),
        "task_capacity_bits": (None if bound == math.inf
                               else round(policy.task_capacity_bits(), 4)),
        "residual_after_canonicalisation": (
            "Canonicalising every per-release dimension does not reach zero: a "
            "workload still chooses how many times to release, and the count is "
            "visible. task_capacity_bits states that remainder rather than "
            "omitting it."
        ),
        "interpretation": (
            "conveyed_bits counts distinct traces an external observer could "
            "distinguish, so it is an upper bound that assumes a perfect observer "
            "and an optimal decoder. It measures this interface under this policy "
            "and this encoder; it is not a proof that no other encoder does better, "
            "and it says nothing about channels outside the mediated release path."
        ),
    }


def canonical_policy(destinations: tuple[str, ...], paths: tuple[str, ...],
                     *, contract_destination: str, contract_path: str) -> EgressPolicy:
    """The policy an institution should deploy: every removable choice removed.

    Destination and path come from the task contract, emission runs on a coarse
    grid, and sizes are padded to four buckets. What remains is charged.
    """
    return EgressPolicy(
        approved_destinations=destinations,
        approved_paths=paths,
        contract_destination=contract_destination,
        contract_path=contract_path,
        schedule_seconds=900.0,
        size_buckets=(4096, 16384, 65536, 262144),
        budget_bits=8.0,
    )


def sealed_policy(destinations: tuple[str, ...], paths: tuple[str, ...],
                  *, contract_destination: str, contract_path: str,
                  releases: int = 2) -> EgressPolicy:
    """Every dimension canonical and the count fixed: the channel closes.

    This is the strongest setting and it is not free. A fixed release count
    means cover traffic, a single size bucket means padding every artifact to
    the largest, and a coarse schedule means a real result can wait. An
    institution should reach for it where a leak matters more than latency, and
    the measurement below says exactly what it buys.
    """
    return EgressPolicy(
        approved_destinations=destinations,
        approved_paths=paths,
        contract_destination=contract_destination,
        contract_path=contract_path,
        schedule_seconds=3600.0,
        size_buckets=(262144,),
        budget_bits=float(releases),
        fixed_releases=releases,
    )


__all__ = [
    "DIMENSIONS", "ChoicePoint", "EgressBudgetExhausted", "EgressChannel",
    "EgressDenied", "EgressPolicy", "Encoder", "Observable", "ReleaseRequest",
    "benign_workflow", "canonical_policy", "conveyed_bits", "positional_encoder",
    "run_channel_experiment", "sealed_policy",
]
