"""Remote effects that a local transaction cannot make exactly-once.

The runtime's effect path is exactly-once inside its own database. The moment an
effect leaves the process -- a payment, an enrolment, a message to a registrar
system -- that guarantee ends, and it ends in the most dangerous way: the call
that times out may have succeeded. Retrying is a double effect. Not retrying is
a lost effect. Reporting either as success is a false record.

This module refuses to pretend. It gives every outbound effect a deterministic
idempotency key derived from the approved proposal, writes the intent durably
*before* the call, and treats an unacknowledged call as ``UNCERTAIN`` -- a first
class state, not an error to swallow. An uncertain effect is never retried
blindly: it is reconciled against the provider by key, and until it resolves it
blocks the authority that depends on it.

The honest boundary is stated in one line and enforced in code: **this makes a
remote effect at-most-once with attributable reconciliation, and
exactly-once-observable only when the provider supports lookup by idempotency
key.** A provider without that lookup leaves a permanent uncertain remainder,
and ``reconcile`` says so rather than guessing.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

INTENT = "INTENT"
SENT = "SENT"
CONFIRMED = "CONFIRMED"
FAILED = "FAILED"
UNCERTAIN = "UNCERTAIN"
TERMINAL = (CONFIRMED, FAILED)


class RemoteEffectError(RuntimeError):
    """Base class for outbound effect failures. Carries a stable code."""

    code = "REMOTE_EFFECT_ERROR"


class LostAcknowledgement(RemoteEffectError):
    """The call may or may not have taken effect. Never treated as failure."""

    code = "LOST_ACKNOWLEDGEMENT"


class ProviderRejected(RemoteEffectError):
    """The provider refused the effect. It definitely did not take effect."""

    code = "PROVIDER_REJECTED"


class UnresolvedEffect(RemoteEffectError):
    """An uncertain effect blocks the work that depends on it."""

    code = "UNRESOLVED_EFFECT"


class IntegrityViolation(RemoteEffectError):
    """The provider reported two different results for one idempotency key."""

    code = "PROVIDER_INTEGRITY_VIOLATION"


class RemoteProvider(Protocol):
    """What an integration must supply to be reconcilable.

    ``lookup`` is the whole difference between a system that can recover from a
    lost acknowledgement and one that cannot. A provider that returns ``None``
    for "I do not offer lookup" is recorded as permanently unreconcilable
    rather than assumed successful or assumed failed.
    """

    def submit(self, idempotency_key: str, operation: str, payload: dict) -> dict:
        ...

    def lookup(self, idempotency_key: str) -> dict | None:
        ...


def idempotency_key(*, proposal: str, approval: str, operation: str, payload: dict) -> str:
    """Derive a key from the approved decision, not from the attempt.

    Two retries of one approved proposal share a key. Two *different* approvals
    never do, so an operator who approves the same correction twice on purpose
    gets two effects, which is what they asked for.
    """
    material = json.dumps(
        {"proposal": proposal, "approval": approval, "operation": operation,
         "payload": payload},
        sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode()).hexdigest()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


@dataclass(frozen=True)
class EffectRecord:
    key: str
    operation: str
    state: str
    attempts: int
    payload_digest: str
    result_digest: str | None
    detail: str
    created_at: float
    updated_at: float

    @property
    def resolved(self) -> bool:
        return self.state in TERMINAL

    def to_dict(self) -> dict:
        return {
            "key": self.key, "operation": self.operation, "state": self.state,
            "attempts": self.attempts, "payload_digest": self.payload_digest,
            "result_digest": self.result_digest, "detail": self.detail,
            "created_at": self.created_at, "updated_at": self.updated_at,
        }


class EffectLedger:
    """Durable write-ahead record of every outbound effect and its real state."""

    def __init__(self, path: str | Path, *, clock: Callable[[], float] = time.time) -> None:
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS remote_effects(
                key TEXT PRIMARY KEY, operation TEXT NOT NULL, state TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, payload_digest TEXT NOT NULL,
                result_digest TEXT, detail TEXT NOT NULL DEFAULT '',
                created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
        self._clock = clock

    def close(self) -> None:
        self.db.close()

    # -- reads -------------------------------------------------------------

    def get(self, key: str) -> EffectRecord | None:
        row = self.db.execute(
            "SELECT * FROM remote_effects WHERE key=?", (key,)).fetchone()
        return None if row is None else EffectRecord(**dict(row))

    def unresolved(self) -> tuple[EffectRecord, ...]:
        """Everything that is not yet known to have happened or not happened."""
        rows = self.db.execute(
            "SELECT * FROM remote_effects WHERE state NOT IN (?,?) ORDER BY created_at",
            TERMINAL).fetchall()
        return tuple(EffectRecord(**dict(row)) for row in rows)

    def require_settled(self) -> None:
        """Refuse dependent work while any effect's real state is unknown."""
        pending = self.unresolved()
        if pending:
            raise UnresolvedEffect(
                f"{len(pending)} outbound effect(s) unresolved: "
                + ", ".join(f"{r.key[:12]}={r.state}" for r in pending[:5]))

    # -- writes ------------------------------------------------------------

    def _write(self, key: str, **columns: Any) -> None:
        columns["updated_at"] = self._clock()
        assignments = ", ".join(f"{name}=?" for name in columns)
        self.db.execute(f"UPDATE remote_effects SET {assignments} WHERE key=?",
                        (*columns.values(), key))

    def submit(
        self,
        provider: RemoteProvider,
        *,
        key: str,
        operation: str,
        payload: dict,
    ) -> EffectRecord:
        """Perform an outbound effect at most once, recording what is known.

        The sequence matters and is the point of the module: the intent is
        durable before the call, so a crash at any instant leaves a record that
        says "this may have happened", never silence.
        """
        now = self._clock()
        payload_digest = _digest(payload)
        existing = self.get(key)
        if existing is not None:
            if existing.payload_digest != payload_digest:
                raise IntegrityViolation(
                    "one idempotency key was reused for a different payload")
            if existing.state == CONFIRMED:
                return existing            # already done; the provider is not called
            if existing.state == FAILED:
                return existing            # definitively not done; a retry needs a new approval
            # INTENT, SENT or UNCERTAIN: the previous attempt's fate is unknown,
            # possibly because the process died mid-call. Resending here is the
            # double-effect bug this module exists to prevent.
            if existing.state != UNCERTAIN:
                self._write(key, state=UNCERTAIN,
                            detail="a prior attempt did not complete; state unknown")
            raise UnresolvedEffect(
                f"effect {key[:12]} is unresolved; reconcile before retrying")

        self.db.execute(
            "INSERT INTO remote_effects(key,operation,state,attempts,payload_digest,"
            "created_at,updated_at) VALUES(?,?,?,0,?,?,?)",
            (key, operation, INTENT, payload_digest, now, now))

        self._write(key, state=SENT, attempts=1)
        try:
            result = provider.submit(key, operation, payload)
        except LostAcknowledgement as error:
            self._write(key, state=UNCERTAIN, detail=str(error)[:300])
            return self.get(key)
        except ProviderRejected as error:
            self._write(key, state=FAILED, detail=str(error)[:300])
            return self.get(key)
        except (OSError, TimeoutError) as error:
            # A transport failure is not evidence of non-effect.
            self._write(key, state=UNCERTAIN, detail=f"{type(error).__name__}: {error}"[:300])
            return self.get(key)
        self._write(key, state=CONFIRMED, result_digest=_digest(result), detail="")
        return self.get(key)

    def reconcile(self, provider: RemoteProvider, key: str) -> EffectRecord:
        """Ask the provider what actually happened, by key.

        Reconciliation is idempotent and never invents an answer: a provider
        that cannot answer leaves the effect uncertain and says why.
        """
        record = self.get(key)
        if record is None:
            raise UnresolvedEffect(f"no record for {key[:12]}")
        if record.resolved:
            return record
        try:
            found = provider.lookup(key)
        except (OSError, TimeoutError, RemoteEffectError) as error:
            self._write(key, detail=f"reconciliation unavailable: {error}"[:300])
            return self.get(key)
        if found is None:
            self._write(
                key, detail="provider reports no record for this key; it may not "
                            "offer lookup, so the effect stays uncertain")
            return self.get(key)
        if found.get("status") == "absent":
            self._write(key, state=FAILED, detail="provider confirms no such effect")
            return self.get(key)
        result_digest = _digest(found.get("result"))
        if record.result_digest is not None and record.result_digest != result_digest:
            self._write(key, state=UNCERTAIN,
                        detail="provider returned a different result for one key")
            raise IntegrityViolation(
                f"provider result changed for key {key[:12]}")
        self._write(key, state=CONFIRMED, result_digest=result_digest,
                    detail="resolved by reconciliation")
        return self.get(key)

    def reconcile_all(self, provider: RemoteProvider) -> dict:
        """Reconcile every unresolved effect and report what remains."""
        resolved, remaining, violations = [], [], []
        for record in self.unresolved():
            try:
                after = self.reconcile(provider, record.key)
            except IntegrityViolation as error:
                violations.append({"key": record.key, "detail": str(error)})
                continue
            (resolved if after.resolved else remaining).append(after.to_dict())
        return {
            "schema_version": "1.0",
            "kind": "remote_effect_reconciliation",
            "resolved": resolved,
            "still_uncertain": remaining,
            "integrity_violations": violations,
            "limits": [
                "at-most-once delivery with reconciliation; exactly-once-observable "
                "only where the provider supports lookup by idempotency key",
                "an effect that stays uncertain is a real operational state and "
                "requires a named human to settle it",
                "committed remote effects are not recalled by this module",
            ],
        }


__all__ = [
    "CONFIRMED", "FAILED", "INTENT", "SENT", "TERMINAL", "UNCERTAIN",
    "EffectLedger", "EffectRecord", "IntegrityViolation", "LostAcknowledgement",
    "ProviderRejected", "RemoteEffectError", "RemoteProvider", "UnresolvedEffect",
    "idempotency_key",
]
