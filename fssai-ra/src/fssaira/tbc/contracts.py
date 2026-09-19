"""Strict, JSON-serializable authority declarations for the TBC SDK.

Declarations are installed by the trusted control service, never accepted as
part of a model proposal. All identifiers are exact matches, with no wildcards.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields

AXES = ("models", "data_classes", "zones", "tools", "resources", "destinations",
        "operations", "channels", "memory")
PRIMITIVES = frozenset({"request_context", "request_capability", "invoke_tool", "persist_memory",
                        "read_memory", "propose_effect", "execute_effect", "release_artifact",
                        "derive_artifact", "spawn_agent", "send_message", "receive_message"})
BUDGETS = ("calls", "context_bytes", "memory_bytes", "traffic_bytes", "compute_units", "cost_microunits")


class AuthorityDenied(ValueError):
    """A stable reason code, never untrusted input or protected values."""


def require(condition, code):
    if not condition:
        raise AuthorityDenied(code)


def identifier(value):
    require(isinstance(value, str) and 0 < len(value) <= 160 and value.strip() == value
            and "*" not in value and all(ord(c) >= 32 for c in value), "INVALID_IDENTIFIER")
    return value


def integer(value, minimum=0):
    require(type(value) is int and minimum <= value <= 2**53, "INVALID_INTEGER")
    return value


@dataclass(frozen=True)
class Scope:
    models: frozenset[str]
    data_classes: frozenset[str]
    zones: frozenset[str]
    tools: frozenset[str]
    resources: frozenset[str]
    destinations: frozenset[str]
    operations: frozenset[str]
    channels: frozenset[str]
    memory: frozenset[str]

    def __post_init__(self):
        for axis in AXES:
            values = getattr(self, axis)
            require(isinstance(values, (set, frozenset, list, tuple))
                    and len(values) <= 128, "INVALID_SCOPE")
            object.__setattr__(self, axis, frozenset(identifier(v) for v in values))
        require(self.operations <= PRIMITIVES, "UNKNOWN_PRIMITIVE")

    @classmethod
    def parse(cls, value):
        require(isinstance(value, dict) and set(value) == set(AXES), "INVALID_SCOPE_FIELDS")
        return cls(**value)

    def to_dict(self):
        return {axis: sorted(getattr(self, axis)) for axis in AXES}

    def subset(self, parent):
        return all(getattr(self, axis) <= getattr(parent, axis) for axis in AXES)

    def intersect(self, other):
        return Scope(**{axis: getattr(self, axis) & getattr(other, axis) for axis in AXES})


@dataclass(frozen=True)
class Budget:
    calls: int
    context_bytes: int
    memory_bytes: int
    traffic_bytes: int
    compute_units: int
    cost_microunits: int

    def __post_init__(self):
        for item in fields(self):
            integer(getattr(self, item.name))

    @classmethod
    def parse(cls, value):
        require(isinstance(value, dict) and set(value) == set(BUDGETS), "INVALID_BUDGET_FIELDS")
        return cls(**value)

    def to_dict(self):
        return asdict(self)

    def subset(self, parent):
        return all(getattr(self, k) <= getattr(parent, k) for k in BUDGETS)


@dataclass(frozen=True)
class Passport:
    workload: str
    owner: str
    scope: Scope
    budget: Budget
    inventory: tuple[str, ...]
    max_agents: int
    max_depth: int
    lease_seconds: int
    memory_retention_seconds: int
    policy_version: int
    safe_state: str = "QUARANTINED"

    def __post_init__(self):
        identifier(self.workload)
        identifier(self.owner)
        for name in ("max_agents", "lease_seconds", "memory_retention_seconds", "policy_version"):
            integer(getattr(self, name), 1)
        integer(self.max_depth)
        require(self.max_agents <= 256 and self.max_depth <= 16, "POPULATION_BOUND_TOO_LARGE")
        require(self.safe_state == "QUARANTINED", "UNSAFE_FAILURE_STATE")
        object.__setattr__(self, "inventory", tuple(sorted({identifier(v) for v in self.inventory})))
        require(self.scope.operations <= set(self.inventory) <= PRIMITIVES, "INCOMPLETE_INVENTORY")

    @classmethod
    def parse(cls, value):
        require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
                "INVALID_PASSPORT_FIELDS")
        return cls(**{**value, "scope": Scope.parse(value["scope"]),
                      "budget": Budget.parse(value["budget"])})

    def to_dict(self):
        return {**asdict(self), "scope": self.scope.to_dict(), "budget": self.budget.to_dict(),
                "inventory": list(self.inventory)}


@dataclass(frozen=True)
class TaskContract:
    task: str
    purpose: str
    subject: str
    tenant: str
    scope: Scope
    budget: Budget
    expires: int

    def __post_init__(self):
        for key in ("task", "purpose", "subject", "tenant"):
            identifier(getattr(self, key))
        integer(self.expires, 1)

    @classmethod
    def parse(cls, value):
        require(isinstance(value, dict) and set(value) == {f.name for f in fields(cls)},
                "INVALID_TASK_FIELDS")
        return cls(**{**value, "scope": Scope.parse(value["scope"]),
                      "budget": Budget.parse(value["budget"])})

    def to_dict(self):
        return {**asdict(self), "scope": self.scope.to_dict(), "budget": self.budget.to_dict()}
