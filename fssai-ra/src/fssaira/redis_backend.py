"""Redis-backed ports for a multi-process FSSAI-RA control plane."""
from __future__ import annotations

import json
import time
from dataclasses import asdict

from .control_plane import ObjectStore
from .evidence import GENESIS_HASH, EvidenceRecord, _digest
from .exact_action import ActionProposal, ExecutionDenied, ExecutionResult, PendingOutcome


def connect_redis(url: str):
    try:
        import redis
    except ImportError as exc:  # pragma: no cover
        raise ImportError("Redis backend requires the 'redis' extra") from exc
    return redis.Redis.from_url(url, decode_responses=True)


class RedisObjectStore(ObjectStore):
    def __init__(self, client, prefix: str = "fssaira") -> None:
        self.client, self.prefix = client, prefix

    def _key(self, namespace: str) -> str:
        return f"{self.prefix}:objects:{namespace}"

    def put(self, namespace: str, key: str, value: dict) -> None:
        self.client.hset(self._key(namespace), key, json.dumps(value, sort_keys=True))

    def get(self, namespace: str, key: str) -> dict | None:
        value = self.client.hget(self._key(namespace), key)
        return None if value is None else json.loads(value)


class RedisApprovalUseStore:
    def __init__(self, client, prefix: str = "fssaira") -> None:
        self.client, self.key = client, f"{prefix}:approval-uses"

    def bind(self, approval_id: str, request_id: str) -> tuple[str, bool]:
        created = bool(self.client.hsetnx(self.key, approval_id, request_id))
        return str(self.client.hget(self.key, approval_id)), created


class RedisPendingOutcomeStore:
    def __init__(self, client, prefix: str = "fssaira") -> None:
        self.client, self.key = client, f"{prefix}:pending-outcomes"

    def put(self, outcome: PendingOutcome) -> None:
        self.client.hset(self.key, outcome.request_id, json.dumps(asdict(outcome), sort_keys=True))

    def remove(self, request_id: str) -> None:
        self.client.hdel(self.key, request_id)

    def get(self, request_id: str) -> PendingOutcome | None:
        value = self.client.hget(self.key, request_id)
        return None if value is None else PendingOutcome(**json.loads(value))

    def values(self) -> tuple[PendingOutcome, ...]:
        return tuple(PendingOutcome(**json.loads(value)) for value in self.client.hvals(self.key))

    def __len__(self) -> int:
        return int(self.client.hlen(self.key))


class RedisCaseRegister:
    """Atomic version-checked transitions using WATCH/MULTI/EXEC."""

    def __init__(self, client, prefix: str = "fssaira") -> None:
        self.client, self.prefix = client, prefix

    def _case_key(self, case_id: str) -> str:
        return f"{self.prefix}:case:{case_id}"

    def _result_key(self, request_id: str) -> str:
        return f"{self.prefix}:result:{request_id}"

    def seed(self, case_id: str, *, status: str, version: int = 1) -> bool:
        return bool(self.client.set(
            self._case_key(case_id), json.dumps({"status": status, "version": version}), nx=True
        ))

    def get(self, case_id: str) -> dict:
        value = self.client.get(self._case_key(case_id))
        if value is None:
            raise KeyError(case_id)
        return json.loads(value)

    def result_for(self, request_id: str) -> ExecutionResult | None:
        value = self.client.get(self._result_key(request_id))
        return None if value is None else ExecutionResult(**json.loads(value))

    @property
    def mutation_count(self) -> int:
        return int(self.client.get(f"{self.prefix}:mutation-count") or 0)

    def transition(self, proposal: ActionProposal) -> ExecutionResult:
        import hashlib

        import redis
        result = ExecutionResult(
            request_id=proposal.request_id,
            case_id=proposal.case_id,
            version=proposal.expected_version + 1,
            status=proposal.to_status,
            receipt_hash=hashlib.sha256(json.dumps({
                "case_id": proposal.case_id, "request_id": proposal.request_id,
                "status": proposal.to_status, "version": proposal.expected_version + 1,
            }, sort_keys=True, separators=(",", ":")).encode()).hexdigest(),
        )
        case_key = self._case_key(proposal.case_id)
        result_key = self._result_key(proposal.request_id)
        while True:
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(case_key, result_key)
                    prior = pipe.get(result_key)
                    if prior is not None:
                        pipe.unwatch()
                        return ExecutionResult(**{**json.loads(prior), "replayed": True})
                    raw = pipe.get(case_key)
                    if raw is None:
                        pipe.unwatch()
                        raise ExecutionDenied("CASE_NOT_FOUND", "the target resource does not exist")
                    item = json.loads(raw)
                    if item["version"] != proposal.expected_version:
                        pipe.unwatch()
                        raise ExecutionDenied(
                            "CASE_VERSION_CONFLICT",
                            "the reviewed resource version is no longer current",
                        )
                    if item["status"] != proposal.from_status:
                        pipe.unwatch()
                        raise ExecutionDenied(
                            "CASE_STATE_CONFLICT",
                            "the reviewed starting state is no longer current",
                        )
                    pipe.multi()
                    pipe.set(case_key, json.dumps({
                        "status": proposal.to_status,
                        "version": proposal.expected_version + 1,
                    }, sort_keys=True))
                    pipe.set(result_key, json.dumps(asdict(result), sort_keys=True))
                    pipe.incr(f"{self.prefix}:mutation-count")
                    pipe.execute()
                    return result
            except redis.WatchError:
                continue


class RedisEvidenceLedger:
    """Hash-chained evidence persisted as a Redis list with optimistic locking."""

    def __init__(self, client, append_token: str, prefix: str = "fssaira") -> None:
        if not append_token:
            raise ValueError("append_token must be non-empty")
        self.client, self.token = client, append_token
        self.key = f"{prefix}:evidence"

    def append(self, kind: str, payload: dict, *, token: str) -> EvidenceRecord:
        if token != self.token:
            raise PermissionError("no evidence write authority")
        import redis
        while True:
            try:
                with self.client.pipeline() as pipe:
                    pipe.watch(self.key)
                    seq = int(pipe.llen(self.key))
                    last = pipe.lindex(self.key, -1)
                    prev = GENESIS_HASH if last is None else json.loads(last)["hash"]
                    ts = time.time()
                    record = EvidenceRecord(seq, ts, kind, payload, prev, _digest(seq, ts, kind, payload, prev))
                    pipe.multi()
                    pipe.rpush(self.key, json.dumps(asdict(record), sort_keys=True))
                    pipe.execute()
                    return record
            except redis.WatchError:
                continue

    def _records(self) -> list[EvidenceRecord]:
        return [EvidenceRecord(**json.loads(value)) for value in self.client.lrange(self.key, 0, -1)]

    def verify(self) -> bool:
        prev = GENESIS_HASH
        for index, record in enumerate(self._records()):
            if record.seq != index or record.prev_hash != prev:
                return False
            if _digest(record.seq, record.ts, record.kind, record.payload, record.prev_hash) != record.hash:
                return False
            prev = record.hash
        return True

    def find(self, kind: str | None = None, **match) -> list[EvidenceRecord]:
        return [record for record in self._records()
                if (kind is None or record.kind == kind)
                and all(record.payload.get(key) == value for key, value in match.items())]

    def __iter__(self):
        return iter(self._records())

    def __len__(self) -> int:
        return int(self.client.llen(self.key))
