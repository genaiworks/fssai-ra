"""Plugin registry: how a third party adds a backend without forking the core.

Three ways to register an implementation, in increasing order of decoupling:

1. **In-process** -- ``register("model", "my-model", factory)`` at import time.
2. **Dotted path** -- ``FSSAI_MODEL=mypkg.models:MyModel`` in the environment.
3. **Entry points** -- declare ``[project.entry-points."fssaira.models"]`` in your
   own ``pyproject.toml``; installing your package makes the backend visible to
   ``fssaira plugins`` with no configuration at all.

Every registry is keyed by a *port name* from :mod:`fssaira.ports`, and every
factory is called with keyword arguments only, so adding a parameter to the
reference adapters never breaks a third-party one.

The point of this indirection is assurance, not fashion: an institution must be
able to swap Redis for its own state store, Ollama for its own model, or the
software diode for a certified appliance, and then *re-run the same conformance
suite* to show the control properties still hold.
"""
from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from importlib import import_module
from typing import Any

PORTS = (
    "model",        # fssaira.ports.ModelBackendPort
    "register",     # fssaira.ports.RegisterPort
    "evidence",     # fssaira.ports.EvidencePort
    "objects",      # fssaira.ports.ObjectStorePort
    "events",       # fssaira.ports.EventBus
    "snapshots",    # fssaira.ports.SnapshotStoreLike
    "inward",       # fssaira.ports.InwardChannel
)

ENTRY_POINT_GROUPS = {port: f"fssaira.{port}s" for port in PORTS}


class PluginError(RuntimeError):
    """Raised when a plugin cannot be found, loaded, or does not fit its port."""


@dataclass(frozen=True)
class PluginInfo:
    port: str
    name: str
    origin: str
    summary: str = ""


_REGISTRY: dict[str, dict[str, Callable[..., Any]]] = {port: {} for port in PORTS}
_ORIGINS: dict[tuple[str, str], str] = {}
_SUMMARIES: dict[tuple[str, str], str] = {}


def register(
    port: str,
    name: str,
    factory: Callable[..., Any],
    *,
    origin: str = "in-process",
    summary: str = "",
    replace: bool = False,
) -> None:
    """Register ``factory`` as the implementation ``name`` of ``port``."""
    if port not in _REGISTRY:
        raise PluginError(f"unknown port {port!r}; expected one of {', '.join(PORTS)}")
    if not callable(factory):
        raise PluginError(f"plugin {port}:{name} factory is not callable")
    if name in _REGISTRY[port] and not replace:
        raise PluginError(f"plugin {port}:{name} is already registered")
    _REGISTRY[port][name] = factory
    _ORIGINS[(port, name)] = origin
    _SUMMARIES[(port, name)] = summary or (factory.__doc__ or "").strip().splitlines()[0:1] and (
        (factory.__doc__ or "").strip().splitlines()[0]
    ) or ""


def unregister(port: str, name: str) -> None:
    _REGISTRY.get(port, {}).pop(name, None)
    _ORIGINS.pop((port, name), None)
    _SUMMARIES.pop((port, name), None)


def _load_entry_points(port: str) -> None:
    """Discover installed third-party plugins for one port. Never raises."""
    group = ENTRY_POINT_GROUPS[port]
    try:
        from importlib.metadata import entry_points

        found: Iterable = entry_points(group=group)
    except Exception:  # pragma: no cover - importlib variance across runtimes
        return
    for entry in found:
        if entry.name in _REGISTRY[port]:
            continue
        try:
            factory = entry.load()
        except Exception as exc:  # pragma: no cover - broken third-party package
            _SUMMARIES[(port, entry.name)] = f"failed to load: {exc}"
            continue
        register(port, entry.name, factory, origin=f"entry-point:{group}", replace=True)


def load_dotted(path: str) -> Callable[..., Any]:
    """Resolve ``package.module:Attribute`` (or ``package.module.Attribute``)."""
    module_name, _, attribute = path.partition(":")
    if not attribute:
        module_name, _, attribute = path.rpartition(".")
    if not module_name or not attribute:
        raise PluginError(f"cannot parse plugin path {path!r}; use 'module:Attribute'")
    try:
        module = import_module(module_name)
    except ImportError as exc:
        raise PluginError(f"cannot import {module_name!r}: {exc}") from exc
    try:
        return getattr(module, attribute)
    except AttributeError as exc:
        raise PluginError(f"{module_name!r} has no attribute {attribute!r}") from exc


def get(port: str, name: str) -> Callable[..., Any]:
    """Return a factory. ``name`` may be a registered name or a dotted path."""
    if port not in _REGISTRY:
        raise PluginError(f"unknown port {port!r}")
    if name not in _REGISTRY[port]:
        _load_entry_points(port)
    if name in _REGISTRY[port]:
        return _REGISTRY[port][name]
    if ":" in name or "." in name:
        factory = load_dotted(name)
        register(port, name, factory, origin="dotted-path", replace=True)
        return factory
    available = ", ".join(sorted(_REGISTRY[port])) or "(none)"
    raise PluginError(f"no {port} plugin named {name!r}; available: {available}")


def create(port: str, name: str, **kwargs: Any) -> Any:
    """Instantiate a plugin. Keyword arguments only, by design."""
    factory = get(port, name)
    try:
        return factory(**kwargs)
    except TypeError as exc:
        raise PluginError(f"plugin {port}:{name} rejected its configuration: {exc}") from exc


def available(port: str | None = None) -> list[PluginInfo]:
    """List every plugin the process can see, including installed entry points."""
    ports = PORTS if port is None else (port,)
    out: list[PluginInfo] = []
    for one in ports:
        if one not in _REGISTRY:
            raise PluginError(f"unknown port {one!r}")
        _load_entry_points(one)
        for name in sorted(_REGISTRY[one]):
            out.append(PluginInfo(
                port=one,
                name=name,
                origin=_ORIGINS.get((one, name), "unknown"),
                summary=_SUMMARIES.get((one, name), ""),
            ))
    return out


def configured_name(port: str, default: str) -> str:
    """Read ``FSSAI_<PORT>`` from the environment, falling back to ``default``."""
    return os.getenv(f"FSSAI_{port.upper()}", default)


def fits(instance: Any, protocol: type) -> bool:
    """Structural check used by the conformance suite before it runs a backend."""
    return isinstance(instance, protocol)


def _install_reference_plugins() -> None:
    """Register the adapters that ship with this repository (lazy factories)."""

    def _memory_register(**kw):
        from .exact_action import CaseRegister

        return CaseRegister(kw.pop("cases", {}) or {})

    def _memory_evidence(**kw):
        from .evidence import EvidenceLedger

        return EvidenceLedger(kw.get("append_token", "teaching-evidence-writer"))

    def _memory_objects(**kw):
        from .control_plane import MemoryObjectStore

        return MemoryObjectStore()

    def _memory_events(**kw):
        from .event_transport import EventLog

        return EventLog()

    def _memory_snapshots(**kw):
        from .reproducible_data import SnapshotStore

        return SnapshotStore()

    def _memory_inward(**kw):
        from .diode import OneWayChannel

        return OneWayChannel()

    def _redis_register(**kw):
        from .redis_backend import RedisCaseRegister, connect_redis

        return RedisCaseRegister(kw.get("client") or connect_redis(kw["url"]), kw.get("prefix", "fssaira"))

    def _redis_evidence(**kw):
        from .redis_backend import RedisEvidenceLedger, connect_redis

        return RedisEvidenceLedger(
            kw.get("client") or connect_redis(kw["url"]),
            kw.get("append_token", "teaching-evidence-writer"),
            kw.get("prefix", "fssaira"),
        )

    def _redis_objects(**kw):
        from .redis_backend import RedisObjectStore, connect_redis

        return RedisObjectStore(kw.get("client") or connect_redis(kw["url"]), kw.get("prefix", "fssaira"))

    def _kafka_events(**kw):
        from .kafka_backend import KafkaEventPublisher

        return KafkaEventPublisher(kw["bootstrap_servers"], kw.get("topic", "fssaira.events"))

    def _postgres_register(**kw):
        from .postgres_backend import PostgresCaseRegister

        return PostgresCaseRegister(kw["dsn"], schema=kw.get("schema", "fssaira"))

    def _postgres_evidence(**kw):
        from .postgres_backend import PostgresEvidenceLedger

        return PostgresEvidenceLedger(
            kw["dsn"], kw.get("append_token", "teaching-evidence-writer"), schema=kw.get("schema", "fssaira")
        )

    def _postgres_objects(**kw):
        from .postgres_backend import PostgresObjectStore

        return PostgresObjectStore(kw["dsn"], schema=kw.get("schema", "fssaira"))

    def _iceberg_snapshots(**kw):
        from .iceberg_backend import IcebergSnapshotStore

        return IcebergSnapshotStore(**kw)

    def _udp_diode(**kw):
        from .diode_transport import UdpDiodeSender

        return UdpDiodeSender(**kw)

    entries = {
        "register": {"memory": _memory_register, "redis": _redis_register, "postgres": _postgres_register},
        "evidence": {"memory": _memory_evidence, "redis": _redis_evidence, "postgres": _postgres_evidence},
        "objects": {"memory": _memory_objects, "redis": _redis_objects, "postgres": _postgres_objects},
        "events": {"memory": _memory_events, "kafka": _kafka_events},
        "snapshots": {"memory": _memory_snapshots, "iceberg": _iceberg_snapshots},
        "inward": {"memory": _memory_inward, "udp-diode": _udp_diode},
    }
    summaries = {
        ("register", "postgres"): "durable register with a transactional outbox",
        ("inward", "udp-diode"): "unidirectional UDP send with no return path",
        ("snapshots", "iceberg"): "Apache Iceberg snapshots and time travel",
    }
    for port, items in entries.items():
        for name, factory in items.items():
            register(port, name, factory, origin="built-in",
                     summary=summaries.get((port, name), ""), replace=True)


_install_reference_plugins()

__all__ = [
    "PORTS", "ENTRY_POINT_GROUPS", "PluginError", "PluginInfo",
    "register", "unregister", "get", "create", "available",
    "load_dotted", "configured_name", "fits",
]
