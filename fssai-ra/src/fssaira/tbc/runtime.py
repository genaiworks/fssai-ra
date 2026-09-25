"""Persistent service-side mediation for the mechanisms in TBC v11.

The untrusted interface is dispatch(token, JSON). Administrative methods require
an independently provisioned authority token. Python objects, SQLite and adapter
code belong to the trusted service; this is not a sandbox for hostile Python.
All effects are local transactions. No arbitrary URL, shell, SQL, or tool callback
is accepted. See the engineering guide for deployment isolation requirements.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from contextlib import contextmanager, suppress

from ..integration.messages import parse_sdk_request
from ..joined_workflow import Denied, Workflow, canonical, digest
from .contracts import (
    BUDGETS,
    PRIMITIVES,
    AuthorityDenied,
    Passport,
    Scope,
    TaskContract,
    identifier,
    integer,
    require,
)

# Nested sets make contraction monotone even when switching named modes.
MODES = {
    "NORMAL": PRIMITIVES,
    "RESTRICTED": PRIMITIVES - {"spawn_agent", "invoke_tool", "send_message"},
    "PROPOSAL_ONLY": frozenset({"request_context", "request_capability", "read_memory",
                                "derive_artifact", "propose_effect", "receive_message"}),
    "READ_ONLY": frozenset({"request_context", "request_capability", "read_memory", "receive_message"}),
    "QUARANTINED": frozenset(),
}
SCHEMAS = {
    "request_capability": {"op", "scope", "ttl"},
    "request_context": {"op", "capability", "resource"},
    "derive_artifact": {"op", "capability", "text"},
    "invoke_tool": {"op", "capability", "tool", "artifact", "max_chars"},
    "persist_memory": {"op", "capability", "artifact", "namespace", "retention"},
    "read_memory": {"op", "capability", "memory"},
    "propose_effect": {"op", "capability", "context", "operation", "value", "recipient"},
    "execute_effect": {"op", "capability", "proposal", "approval"},
    "release_artifact": {"op", "capability", "artifact", "destination", "escrow"},
    "spawn_agent": {"op", "capability", "scope", "model", "zone", "ttl"},
    "send_message": {"op", "capability", "recipient", "channel", "artifact"},
    "receive_message": {"op", "capability", "message"},
}


def _token_hash(token):
    require(isinstance(token, str) and 0 < len(token) <= 512, "AUTHENTICATION_REQUIRED")
    return hashlib.sha256(token.encode()).hexdigest()


class TrustRuntime:
    """Trusted control service. Construct once per connection/process.

    ``authorities`` maps opaque tokens to (named identity, role). Roles are
    operator, reviewer, source, recipient. Do not pass this object to model code;
    give the model only an authenticated dispatch transport (or SDKClient).
    ``clock`` is a trusted service clock, injectable for deterministic tests.
    ``min_deliberation_seconds`` is the minimum review time: an approval issued
    sooner after its proposal is deferred to the manual route (0 disables it).
    ``receipt_retention_seconds`` bounds how long decision receipts are kept
    (None keeps them until an operator prunes with an explicit horizon).
    """

    def __init__(self, path, passport: Passport, *, authorities, clock=None, pack="education",
                 min_deliberation_seconds=0, receipt_retention_seconds=None):
        self.clock = clock or (lambda: int(time.time()))
        self.passport = passport
        self.min_deliberation_seconds = integer(min_deliberation_seconds)
        self.receipt_retention_seconds = (None if receipt_retention_seconds is None
                                          else integer(receipt_retention_seconds, 1))
        self.authorities = {}
        for token, (name, role) in authorities.items():
            identifier(name)
            require(role in {"operator", "reviewer", "source", "recipient", "monitor"}, "UNKNOWN_ROLE")
            self.authorities[_token_hash(token)] = (name, role)
        self.world = Workflow(path, pack=pack, mediator="tbc")
        self.db = self.world.db
        self.db.executescript('''
        CREATE INDEX IF NOT EXISTS tbc_evidence_task_seq
          ON evidence(json_extract(body, '$.data.task'), seq);
        CREATE TABLE IF NOT EXISTS tbc_supervision(id INTEGER PRIMARY KEY CHECK(id=1), stopped INTEGER);
        INSERT OR IGNORE INTO tbc_supervision VALUES(1,0);
        CREATE TABLE IF NOT EXISTS tbc_delivery(id TEXT PRIMARY KEY, binding TEXT, position INTEGER, mode TEXT);
        CREATE TABLE IF NOT EXISTS tbc_invalid_sources(binding TEXT PRIMARY KEY, reason TEXT, operator TEXT);
        CREATE TABLE IF NOT EXISTS tbc_usage(id INTEGER PRIMARY KEY CHECK(id=1), remaining TEXT);
        CREATE TABLE IF NOT EXISTS tbc_config(id INTEGER PRIMARY KEY CHECK(id=1), body TEXT);
        CREATE TABLE IF NOT EXISTS tbc_tasks(id TEXT PRIMARY KEY, body TEXT, remaining TEXT,
          state TEXT, epoch INTEGER, runtime_scope TEXT);
        CREATE TABLE IF NOT EXISTS tbc_agents(id TEXT PRIMARY KEY, token TEXT UNIQUE, task TEXT,
          parent TEXT, scope TEXT, model TEXT, zone TEXT, expires INTEGER, revoked INTEGER,
          labels TEXT, sources TEXT);
        CREATE TABLE IF NOT EXISTS tbc_objects(id TEXT PRIMARY KEY, kind TEXT, body TEXT, mac TEXT);
        CREATE TABLE IF NOT EXISTS tbc_edges(task TEXT, source TEXT, target TEXT, channel TEXT,
          PRIMARY KEY(task,source,target,channel));
        CREATE TABLE IF NOT EXISTS tbc_used(id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS tbc_sinks(id TEXT PRIMARY KEY, destination TEXT, bytes BLOB);
        CREATE TABLE IF NOT EXISTS tbc_receipts(seq INTEGER PRIMARY KEY AUTOINCREMENT, task TEXT,
          issued INTEGER, body TEXT, mac TEXT);
        CREATE TABLE IF NOT EXISTS tbc_reservations(id TEXT PRIMARY KEY, task TEXT, amounts TEXT,
          state TEXT, operator TEXT);
        CREATE TABLE IF NOT EXISTS tbc_graph_mode(task TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS tbc_graph_nodes(task TEXT, agent TEXT, PRIMARY KEY(task,agent));
        CREATE TABLE IF NOT EXISTS tbc_graph_edges(task TEXT, source TEXT, target TEXT, channel TEXT,
          PRIMARY KEY(task,source,target,channel));
        CREATE TABLE IF NOT EXISTS tbc_manual_queue(proposal TEXT PRIMARY KEY, task TEXT,
          reviewer TEXT, queued INTEGER, reason TEXT);
        ''')
        try:
            with self.transaction():
                self.db.execute("INSERT OR IGNORE INTO tbc_usage VALUES(1,?)",
                                (canonical(passport.budget.to_dict()),))
                stored = self.db.execute("SELECT body FROM tbc_config WHERE id=1").fetchone()
                config = canonical(passport.to_dict())
                if stored:
                    require(stored[0] == config, "PASSPORT_DRIFT")
                else:
                    self.db.execute("INSERT INTO tbc_config VALUES(1,?)", (config,))
                    self.world.event("tbc_passport", {"digest": digest(passport.to_dict())})
        except Exception:
            self.close()
            raise

    def close(self):
        self.world.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def _admin(self, token, role):
        identity = self.authorities.get(_token_hash(token))
        require(identity is not None and identity[1] == role, "INDEPENDENT_AUTHORITY_REQUIRED")
        return identity[0]

    def _admin_any(self, token, roles):
        identity = self.authorities.get(_token_hash(token))
        require(identity is not None and identity[1] in roles, "INDEPENDENT_AUTHORITY_REQUIRED")
        return identity[0]

    def _now(self):
        return integer(self.clock())

    def _put(self, kind, body):
        oid = secrets.token_hex(24)
        raw = canonical(body)
        mac = hmac.new(bytes.fromhex(self.world.meta("key")),
                       (oid + kind + raw).encode(), hashlib.sha256).hexdigest()
        self.db.execute("INSERT INTO tbc_objects VALUES(?,?,?,?)", (oid, kind, raw, mac))
        return oid

    def _get(self, oid, kind):
        require(isinstance(oid, str), "INVALID_REFERENCE")
        row = self.db.execute("SELECT * FROM tbc_objects WHERE id=? AND kind=?", (oid, kind)).fetchone()
        require(row is not None, "UNKNOWN_REFERENCE")
        mac = hmac.new(bytes.fromhex(self.world.meta("key")),
                       (oid + kind + row["body"]).encode(), hashlib.sha256).hexdigest()
        require(hmac.compare_digest(mac, row["mac"]), "INTEGRITY_FAILURE")
        return json.loads(row["body"])

    def _running(self):
        require(self.db.execute("SELECT stopped FROM tbc_supervision WHERE id=1").fetchone()[0] == 0,
                "WORKLOAD_STOPPED")

    def _task(self, task_id):
        self._running()
        row = self.db.execute("SELECT * FROM tbc_tasks WHERE id=?", (task_id,)).fetchone()
        require(row is not None, "UNKNOWN_TASK")
        task = dict(row)
        task["contract"] = TaskContract.parse(json.loads(task["body"]))
        require(self._now() < task["contract"].expires, "TASK_EXPIRED")
        return task

    def _agent(self, agent_id):
        seen = set()
        current = agent_id
        result = None
        hard = self.passport.scope
        while current:
            require(current not in seen and len(seen) <= self.passport.max_depth, "INVALID_ANCESTRY")
            seen.add(current)
            row = self.db.execute("SELECT * FROM tbc_agents WHERE id=?", (current,)).fetchone()
            require(row is not None and not row["revoked"] and self._now() < row["expires"],
                    "AGENT_REVOKED_OR_EXPIRED")
            if result is None:
                result = dict(row)
            require(row["task"] == result["task"], "CROSS_TASK_ANCESTRY")
            hard = hard.intersect(Scope.parse(json.loads(row["scope"])))
            current = row["parent"]
        require(result is not None, "UNKNOWN_AGENT")
        task = self._task(result["task"])
        hard = hard.intersect(task["contract"].scope)
        effective = hard.intersect(Scope.parse(json.loads(task["runtime_scope"])))
        effective = Scope(**{**effective.to_dict(), "operations": effective.operations & MODES[task["state"]]})
        require(result["model"] in effective.models and result["zone"] in effective.zones,
                "MODEL_OR_ZONE_DENIED")
        self._not_invalidated(json.loads(result["sources"]))
        return result, task, effective

    def _charge(self, task, **charges):
        require(set(charges) <= set(BUDGETS), "UNKNOWN_BUDGET")
        current = json.loads(self.db.execute("SELECT remaining FROM tbc_tasks WHERE id=?", (task["id"],)).fetchone()[0])
        workload = json.loads(self.db.execute("SELECT remaining FROM tbc_usage WHERE id=1").fetchone()[0])
        for key, amount in charges.items():
            integer(amount)
            require(amount <= current[key] and amount <= workload[key], "AGGREGATE_BUDGET_EXHAUSTED")
            current[key] -= amount
            workload[key] -= amount
        self.db.execute("UPDATE tbc_usage SET remaining=? WHERE id=1", (canonical(workload),))
        self.db.execute("UPDATE tbc_tasks SET remaining=? WHERE id=?", (canonical(current), task["id"]))

    def create_task(self, token, contract: TaskContract, *, identity_scope: Scope, model, zone):
        """Enroll a workload from trusted identity/data-rights policy; returns a root bearer token."""
        owner = self._admin(token, "operator")
        require(contract.scope.subset(self.passport.scope) and identity_scope.subset(self.passport.scope),
                "TASK_EXCEEDS_HARD_ENVELOPE")
        require(contract.budget.subset(self.passport.budget), "TASK_BUDGET_EXCEEDS_PASSPORT")
        # The first adapter binds exact canonical institutional resource identities.
        require(contract.purpose == "correction" and contract.tenant == "campus" and contract.subject == "s1"
                and contract.scope.resources == {"campus/s1"}, "UNSUPPORTED_DOMAIN_BINDING")
        require(contract.scope.tools <= {"summarize", "classify"}, "UNREGISTERED_TOOL")
        root_scope = contract.scope.intersect(identity_scope)
        require(model in root_scope.models and zone in root_scope.zones, "MODEL_OR_ZONE_DENIED")
        with self.transaction():
            self._running()
            require(self._now() < contract.expires, "TASK_EXPIRED")
            self.db.execute("INSERT INTO tbc_tasks VALUES(?,?,?,'NORMAL',1,?)",
                            (contract.task, canonical(contract.to_dict()), canonical(contract.budget.to_dict()),
                             canonical(contract.scope.to_dict())))
            agent, secret = self._new_agent(contract.task, "", root_scope, model, zone, contract.expires)
            self.world.event("tbc_task", {"task": contract.task, "owner": owner, "agent": agent,
                                          "contract_digest": digest(contract.to_dict())})
        return {"agent": agent, "token": secret}

    def enroll_agent(self, token, task_id, *, identity_scope, model, zone):
        name = self._admin(token, "operator")
        with self.transaction():
            task = self._task(task_id)
            require(task["state"] == "NORMAL", "ENROLLMENT_RESTRICTED")
            require(identity_scope.subset(self.passport.scope), "IDENTITY_EXCEEDS_PASSPORT")
            scope = task["contract"].scope.intersect(identity_scope)
            require(model in scope.models and zone in scope.zones, "MODEL_OR_ZONE_DENIED")
            agent, secret = self._new_agent(task_id, "", scope, model, zone, task["contract"].expires)
            self.world.event("tbc_enroll", {"task": task_id, "agent": agent, "operator": name})
            return {"agent": agent, "token": secret}

    def _new_agent(self, task, parent, scope, model, zone, expires):
        count = self.db.execute("SELECT count(*) FROM tbc_agents").fetchone()[0]
        require(count < self.passport.max_agents, "POPULATION_LIMIT")
        agent, token = secrets.token_hex(16), secrets.token_urlsafe(32)
        self.db.execute("INSERT INTO tbc_agents VALUES(?,?,?,?,?,?,?,?,0,'[]','[]')",
                        (agent, _token_hash(token), task, parent, canonical(scope.to_dict()), model, zone, expires))
        return agent, token

    def dispatch(self, token, raw):
        """Only model-facing boundary. Authenticated attempts consume call budget.

        A savepoint rolls back denied effects while preserving the attempt and
        its receipt. If evidence itself is unavailable, the outer transaction
        rolls back and returns no data. Anonymous ingress rate limiting belongs
        to the HTTP/service deployment boundary.
        """
        failures = (AuthorityDenied, Denied, ValueError, KeyError, TypeError, RecursionError, sqlite3.Error)
        try:
            with self.transaction():
                row = self.db.execute("SELECT id FROM tbc_agents WHERE token=?", (_token_hash(token),)).fetchone()
                require(row is not None, "AUTHENTICATION_REQUIRED")
                agent, task, scope = self._agent(row[0])
                verdict = Guardian(self)._evaluate_locked(task["id"])
                if verdict["counterexamples"]:
                    # The guardian has already contracted this task inside this
                    # transaction. Raising here would roll that contraction back,
                    # so the refusal is recorded and returned instead, and a
                    # failure to record it never restores the contracted state.
                    with suppress(OSError, ValueError, sqlite3.Error):
                        self.world.event("tbc_blocked_attempt",
                                         {"agent": agent["id"], "task": task["id"],
                                          "code": "ASSURANCE_LOSS"})
                    return {"ok": False, "code": "DENIED"}
                self._charge(task, calls=1)
                q = {}
                self.db.execute("SAVEPOINT tbc_request")
                try:
                    q = parse_sdk_request(raw)
                    require(isinstance(q, dict) and isinstance(q.get("op"), str), "OBJECT_REQUIRED")
                    op = q["op"]
                    require(op in SCHEMAS and not set(q) - SCHEMAS[op], "UNDECLARED_INTERFACE")
                    require(op in scope.operations and op in self.passport.inventory, "ENVELOPE_DENIED")
                    self._require_admitted_node(task["id"], agent["id"])
                    if op != "request_capability":
                        lease = self._get(q["capability"], "capability")
                        require(lease["agent"] == agent["id"] and lease["task"] == task["id"]
                                and lease["epoch"] == task["epoch"] and self._now() < lease["expires"],
                                "STALE_OR_FOREIGN_CAPABILITY")
                        scope = scope.intersect(Scope.parse(lease["scope"]))
                        require(op in scope.operations, "CAPABILITY_SCOPE_DENIED")
                    result = self._handle(op, q, agent, task, scope)
                    self.world.event("tbc_" + op, {"agent": agent["id"], "task": task["id"],
                                                   "request_digest": digest(q), "epoch": task["epoch"]})
                except failures as denial:
                    self.db.execute("ROLLBACK TO tbc_request")
                    self.db.execute("RELEASE tbc_request")
                    self.world.event("tbc_denied", {"agent": agent["id"], "task": task["id"]})
                    self._record_receipt(task, agent, q if isinstance(q, dict) else {}, {}, "DENIED", denial)
                    return {"ok": False, "code": "DENIED"}
                self.db.execute("RELEASE tbc_request")
                self._record_receipt(task, agent, q, result, "ALLOWED")
                return {"ok": True, **result}
        except failures as error:
            # A revoked agent, a stopped workload or an assurance failure is
            # denied before the request savepoint exists, so the inner handler
            # never runs and no evidence would otherwise be written. Silent
            # refusal hides exactly the signal an operator needs after a stop:
            # that something is still trying. The attempt is recorded outside
            # the failed transaction, and a failure to record it never restores
            # authority.
            self._record_blocked_attempt(token, error)
            return {"ok": False, "code": "DENIED"}

    def _record_blocked_attempt(self, token, error):
        """Best-effort evidence that a known identity was refused entry.

        The stored code is the control service's own stable reason, never
        untrusted input, and an unknown token records nothing at all so that
        anonymous traffic cannot be used to grow the evidence chain.
        """
        code = error.args[0] if isinstance(error, AuthorityDenied) and error.args else type(error).__name__
        if not isinstance(code, str) or not code.isidentifier() or len(code) > 64:
            code = "DENIED"
        try:
            row = self.db.execute("SELECT id,task FROM tbc_agents WHERE token=?",
                                  (_token_hash(token),)).fetchone()
            if row is None:
                return
            with self.transaction():
                self.world.event("tbc_blocked_attempt",
                                 {"agent": row["id"], "task": row["task"], "code": code})
        except (AuthorityDenied, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            return

    def _taint(self, agent, labels, sources):
        row = self.db.execute("SELECT labels,sources FROM tbc_agents WHERE id=?", (agent["id"],)).fetchone()
        labels = sorted(set(json.loads(row[0])) | set(labels))
        sources = sorted(set(json.loads(row[1])) | set(sources))
        self.db.execute("UPDATE tbc_agents SET labels=?,sources=? WHERE id=?",
                        (canonical(labels), canonical(sources), agent["id"]))
        return labels, sources

    def _not_invalidated(self, sources):
        for source in sources:
            binding = digest(self.world.get(source, "context"))
            require(self.db.execute("SELECT 1 FROM tbc_invalid_sources WHERE binding=?",
                                    (binding,)).fetchone() is None, "SOURCE_QUARANTINED")

    def invalidate_source(self, token, source, *, reason):
        """Irreversibly quarantine this exact source binding and all tracked derivatives.

        The operator repairs the source under a new version; restore cannot clear
        quarantine. Previously released bytes cannot be recalled.
        """
        name = self._admin(token, "operator")
        require(isinstance(reason, str) and 0 < len(reason.strip()) <= 512, "REASON_REQUIRED")
        with self.transaction():
            binding = digest(self.world.get(source, "context"))
            self.db.execute("INSERT OR IGNORE INTO tbc_invalid_sources VALUES(?,?,?)",
                            (binding, reason, name))
            self.world.event("tbc_source_invalidated", {"binding": binding, "operator": name,
                                                        "reason_digest": digest(reason)})

    def _source_valid(self, sources, scope=None):
        self._not_invalidated(sources)
        for source in sources:
            context = self.world.get(source, "context")
            if scope is not None:
                require(f'{context["tenant"]}/{context["subject"]}' in scope.resources, "RESOURCE_RIGHTS_DENIED")
            self.world.current(context)

    def _artifact(self, artifact_id, agent, task, scope):
        a = self._get(artifact_id, "artifact")
        require(a["task"] == task["id"] and agent["id"] in a["audience"], "ARTIFACT_SCOPE_DENIED")
        require(set(a["labels"]) <= scope.data_classes, "DATA_RIGHTS_DENIED")
        self._source_valid(a["sources"], scope)
        return a

    def _make_artifact(self, agent, task, text, *, labels=(), sources=(), kind="generated", reference=None):
        require(isinstance(text, str) and len(text.encode()) <= 12000, "ARTIFACT_SIZE")
        self._not_invalidated(sources)
        labels, sources = self._taint(agent, labels, sources)
        # producer and epoch give the fan-in gate provenance and freshness to check.
        return self._put("artifact", {"task": task["id"], "audience": [agent["id"]], "text": text,
                                      "labels": labels, "sources": sources, "kind": kind,
                                      "reference": reference, "digest": hashlib.sha256(text.encode()).hexdigest(),
                                      "producer": agent["id"], "epoch": task["epoch"]})

    def _handle(self, op, q, agent, task, scope):
        if op == "request_capability":
            requested = Scope.parse(q.get("scope", scope.to_dict()))
            require(requested.subset(scope), "CAPABILITY_AMPLIFICATION")
            ttl = integer(q.get("ttl", self.passport.lease_seconds), 1)
            require(ttl <= self.passport.lease_seconds, "LEASE_TOO_LONG")
            cid = self._put("capability", {"agent": agent["id"], "task": task["id"],
                         "scope": requested.to_dict(), "epoch": task["epoch"],
                         "expires": min(self._now() + ttl, agent["expires"], task["contract"].expires)})
            return {"capability": cid, "scope": requested.to_dict()}
        if op == "request_context":
            require(q["resource"] in scope.resources and "synthetic-academic" in scope.data_classes,
                    "CONTEXT_SCOPE_DENIED")
            result = self.world.handle("advisor", "advisor", {"op": "read", "tenant": task["contract"].tenant,
                                                               "subject": task["contract"].subject})
            text = canonical({"value": result["value"], "supported": result["supported"]})
            self._charge(task, context_bytes=len(text.encode()))
            artifact = self._make_artifact(agent, task, text, labels=["synthetic-academic"],
                                            sources=[result["context"]], kind="context", reference=result["context"])
            return {"artifact": artifact, "context": artifact, "text": text, "labels": ["synthetic-academic"]}
        if op == "derive_artifact":
            # All previous disclosures taint model output; callers cannot omit lineage.
            self._source_valid(json.loads(agent["sources"]), scope)
            require(set(json.loads(agent["labels"])) <= scope.data_classes, "DATA_RIGHTS_DENIED")
            artifact = self._make_artifact(agent, task, q["text"])
            return {"artifact": artifact}
        if op == "invoke_tool":
            require(q["tool"] in scope.tools and q["tool"] in {"summarize", "classify"}, "TOOL_DENIED")
            a = self._artifact(q["artifact"], agent, task, scope)
            limit = integer(q.get("max_chars", 256), 1)
            require(limit <= 4096, "TOOL_OUTPUT_BOUND")
            self._charge(task, compute_units=len(a["text"].encode()))
            # Deterministic reference adapters, no model runtime or network billing.
            text = a["text"][:limit] if q["tool"] == "summarize" else canonical(a["labels"])
            artifact = self._make_artifact(agent, task, text, labels=a["labels"], sources=a["sources"])
            return {"artifact": artifact, "text": text}
        if op == "persist_memory":
            require(q["namespace"] in scope.memory, "MEMORY_NAMESPACE_DENIED")
            retention = integer(q["retention"], 1)
            require(retention <= self.passport.memory_retention_seconds, "RETENTION_TOO_LONG")
            a = self._artifact(q["artifact"], agent, task, scope)
            self._charge(task, memory_bytes=len(a["text"].encode()))
            mid = self._put("memory", {"artifact": q["artifact"], "task": task["id"],
                    "namespace": q["namespace"], "purpose": task["contract"].purpose,
                    "expires": min(self._now() + retention, task["contract"].expires), "epoch": task["epoch"]})
            return {"memory": mid}
        if op == "read_memory":
            m = self._get(q["memory"], "memory")
            require(m["task"] == task["id"] and m["purpose"] == task["contract"].purpose
                    and m["namespace"] in scope.memory and m["epoch"] == task["epoch"]
                    and self._now() < m["expires"], "MEMORY_REAUTHORIZATION_DENIED")
            a = self._artifact(m["artifact"], agent, task, scope)
            self._charge(task, context_bytes=len(a["text"].encode()))
            self._taint(agent, a["labels"], a["sources"])
            return {"artifact": m["artifact"], "text": a["text"], "labels": a["labels"]}
        if op == "propose_effect":
            a = self._artifact(q["context"], agent, task, scope)
            require(a["kind"] == "context" and q["recipient"] in scope.destinations, "AI_IR_SCOPE_DENIED")
            result = self.world.handle("advisor", "advisor", {"op": "propose", "context": a["reference"],
                               "operation": q["operation"], "value": q["value"], "recipient": q["recipient"]})
            pid = self._put("proposal", {"task": task["id"], "agent": agent["id"],
                                         "epoch": task["epoch"], "joined": result["proposal"],
                                         "created": self._now()})
            joined = self.world.get(result["proposal"], "proposal")
            ir = {"resource": q["context"], "canonical_resource": f'{task["contract"].tenant}/{task["contract"].subject}',
                  "operation": joined["operation"], "expected_version": joined["binding"]["version"],
                  "desired_value": joined["value"], "destination": joined["recipient"]}
            return {"proposal": pid, "digest": result["digest"], "ai_ir": ir}
        if op == "execute_effect":
            p = self._get(q["proposal"], "proposal")
            require(p["task"] == task["id"] and p["agent"] == agent["id"] and p["epoch"] == task["epoch"],
                    "AI_IR_SCOPE_DENIED")
            underlying = self.world.get(p["joined"], "proposal")
            require(underlying["recipient"] in scope.destinations
                    and f'{underlying["binding"]["tenant"]}/{underlying["binding"]["subject"]}' in scope.resources,
                    "AI_IR_SCOPE_DENIED")
            approval = self._get(q["approval"], "approval")
            require(approval["proposal"] == q["proposal"], "EXACT_APPROVAL_REQUIRED")
            result = self.world.handle("advisor", "advisor", {"op": "execute", "proposal": p["joined"],
                                                               "approval": approval["joined"]})
            # Fixed renderer, not model output: bind the committed version to fresh
            # authority while retaining the original proposal in the evidence chain.
            binding = {**underlying["binding"], "version": result["version"]}
            source = self.world.put("context", binding)
            text = canonical({"resource": f'{binding["tenant"]}/{binding["subject"]}',
                              "value": underlying["value"], "version": result["version"]})
            artifact = self._put("artifact", {"task": task["id"], "audience": [agent["id"]],
                       "text": text, "labels": ["synthetic-academic"], "sources": [source],
                       "kind": "executed_effect", "reference": q["proposal"],
                       "digest": hashlib.sha256(text.encode()).hexdigest()})
            return {**result, "artifact": artifact}
        if op == "spawn_agent":
            child_scope = Scope.parse(q["scope"])
            require(child_scope.subset(scope), "DELEGATION_AMPLIFICATION")
            require(q["model"] in child_scope.models and q["zone"] in child_scope.zones, "MODEL_OR_ZONE_DENIED")
            ttl = integer(q["ttl"], 1)
            require(ttl <= self.passport.lease_seconds, "LEASE_TOO_LONG")
            depth, parent = 1, agent
            while parent["parent"]:
                parent = self.db.execute("SELECT * FROM tbc_agents WHERE id=?", (parent["parent"],)).fetchone()
                depth += 1
            require(depth <= self.passport.max_depth, "DELEGATION_DEPTH")
            # Bound total identities over task lifetime, stronger than just concurrent population.
            count = self.db.execute("SELECT count(*) FROM tbc_agents WHERE task=?", (task["id"],)).fetchone()[0]
            require(count < self.passport.max_agents, "POPULATION_LIMIT")
            child, secret = self._new_agent(task["id"], agent["id"], child_scope, q["model"], q["zone"],
                                            min(self._now() + ttl, agent["expires"]))
            return {"agent": child, "token": secret}
        if op == "send_message":
            target, target_task, target_scope = self._agent(q["recipient"])
            require(target_task["id"] == task["id"] and q["channel"] in scope.channels
                    and q["channel"] in target_scope.channels and "receive_message" in target_scope.operations,
                    "AIRLOCK_CHANNEL_DENIED")
            self._require_admitted_edge(task["id"], agent["id"], target["id"], q["channel"])
            a = self._artifact(q["artifact"], agent, task, scope)
            # Prevent composition with a public-capable recipient, even before it reads data.
            require(set(a["labels"]) <= target_scope.data_classes
                    and not (a["labels"] and "public" in target_scope.destinations), "PROHIBITED_FLOW")
            self._charge(task, traffic_bytes=len(a["text"].encode()))
            self.db.execute("INSERT OR IGNORE INTO tbc_edges VALUES(?,?,?,?)",
                            (task["id"], agent["id"], target["id"], q["channel"]))
            require(not Guardian(self)._evaluate_locked(task["id"])["counterexamples"], "PROHIBITED_FLOW")
            clone = {**a, "audience": [target["id"]]}
            aid = self._put("artifact", clone)
            mid = self._put("message", {"task": task["id"], "recipient": target["id"], "artifact": aid,
                                        "epoch": task["epoch"], "sender": agent["id"]})
            return {"message": mid}
        if op == "receive_message":
            m = self._get(q["message"], "message")
            require(m["task"] == task["id"] and m["recipient"] == agent["id"] and m["epoch"] == task["epoch"],
                    "AIRLOCK_RECIPIENT_DENIED")
            self._agent(m["sender"])
            a = self._artifact(m["artifact"], agent, task, scope)
            require(not (a["labels"] and "public" in scope.destinations), "PROHIBITED_FLOW")
            self._charge(task, context_bytes=len(a["text"].encode()))
            self._taint(agent, a["labels"], a["sources"])
            return {"artifact": m["artifact"], "text": a["text"], "labels": a["labels"]}
        if op == "release_artifact":
            a = self._artifact(q["artifact"], agent, task, scope)
            require(q["destination"] in scope.destinations, "DESTINATION_DENIED")
            escrow = self._get(q["escrow"], "escrow")
            require(escrow["artifact"] == q["artifact"] and escrow["digest"] == a["digest"]
                    and escrow["destination"] == q["destination"] and escrow["epoch"] == task["epoch"]
                    and self._now() < escrow["expires"], "EXACT_RELEASE_AUTHORITY_REQUIRED")
            require(not a["labels"] or escrow["declassify"], "DECLASSIFICATION_REQUIRED")
            self.db.execute("INSERT INTO tbc_used VALUES(?)", (q["escrow"],))
            self._charge(task, traffic_bytes=len(a["text"].encode()))
            sid = secrets.token_hex(16)
            self.db.execute("INSERT INTO tbc_sinks VALUES(?,?,?)", (sid, q["destination"], a["text"].encode()))
            binding = self._put("delivery", {"artifact": q["artifact"], "agent": agent["id"],
                        "task": task["id"], "epoch": task["epoch"], "destination": q["destination"],
                        "expires": min(escrow["expires"], self._get(q["capability"], "capability")["expires"]),
                        "digest": a["digest"]})
            self.db.execute("INSERT INTO tbc_delivery VALUES(?,?,0,'pending')", (sid, binding))
            # Model gets a receipt; recipient delivery revalidates current authority.
            return {"receipt": sid, "digest": a["digest"]}
        raise AuthorityDenied("UNIMPLEMENTED_PRIMITIVE")

    def confirm_effect(self, token, proposal):
        name = self._admin(token, "source")
        with self.transaction():
            p = self._get(proposal, "proposal")
            self._agent(p["agent"])
            result = self.world.handle("instructor", "instructor", {"op": "confirm", "proposal": p["joined"]})
            return self._put("confirmation", {"proposal": proposal, "name": name, "joined": result["confirmation"]})

    def approve_effect(self, token, proposal, confirmation):
        name = self._admin(token, "reviewer")
        with self.transaction():
            p, c = self._get(proposal, "proposal"), self._get(confirmation, "confirmation")
            require(c["proposal"] == proposal and c["name"] != name, "INDEPENDENT_CONFIRMATION_REQUIRED")
            _, task, _ = self._agent(p["agent"])
            require(task["epoch"] == p["epoch"], "STALE_PROPOSAL")
            # Minimum review time: an approval faster than the floor is a
            # signature, not oversight, so the work goes to the manual route.
            # Proposals stored before this field existed carry no timestamp.
            deferred = (self.min_deliberation_seconds and p.get("created") is not None
                        and self._now() - p["created"] < self.min_deliberation_seconds)
            if deferred:
                self.db.execute("INSERT OR IGNORE INTO tbc_manual_queue VALUES(?,?,?,?,?)",
                                (proposal, task["id"], name, self._now(), "below_minimum_review_time"))
                self.world.event("tbc_review_deferred", {"task": task["id"], "reviewer": name,
                                                         "route": "manual"})
            else:
                result = self.world.handle("registrar", "registrar", {"op": "approve", "proposal": p["joined"],
                                                                      "confirmation": c["joined"]})
                aid = self._put("approval", {"proposal": proposal, "name": name, "joined": result["approval"]})
                self.world.event("tbc_named_approval", {"approval": aid, "reviewer": name, "source": c["name"]})
                return aid
        # Raised after commit so the manual-route record survives the refusal.
        raise AuthorityDenied("REVIEW_DEFERRED_TO_MANUAL")

    def authorize_release(self, token, artifact, destination, *, declassify=False, ttl=60):
        name = self._admin(token, "reviewer")
        require(type(declassify) is bool, "INVALID_DECLASSIFICATION")
        integer(ttl, 1)
        require(ttl <= self.passport.lease_seconds, "LEASE_TOO_LONG")
        with self.transaction():
            a = self._get(artifact, "artifact")
            agent, task, scope = self._agent(a["audience"][0])
            self._artifact(artifact, agent, task, scope)
            require(destination in scope.destinations and "release_artifact" in scope.operations,
                    "DESTINATION_DENIED")
            escrow = self._put("escrow", {"artifact": artifact, "digest": a["digest"], "destination": destination,
                          "epoch": task["epoch"], "declassify": declassify, "reviewer": name,
                          "expires": min(self._now() + ttl, task["contract"].expires)})
            self.world.event("tbc_release_authorized", {"escrow": escrow, "reviewer": name,
                                                       "declassify": declassify, "digest": a["digest"]})
            return escrow

    def _delivery(self, name, receipt):
        row = self.db.execute("SELECT * FROM tbc_delivery WHERE id=?", (receipt,)).fetchone()
        require(row is not None, "DELIVERY_BINDING_REQUIRED")
        binding = self._get(row["binding"], "delivery")
        require(binding["destination"] == name and self._now() < binding["expires"], "DELIVERY_DENIED")
        agent, task, scope = self._agent(binding["agent"])
        require(binding["task"] == task["id"] and binding["epoch"] == task["epoch"]
                and name in scope.destinations and "release_artifact" in scope.operations, "DELIVERY_REVOKED")
        artifact = self._artifact(binding["artifact"], agent, task, scope)
        sink = self.db.execute("SELECT destination,bytes FROM tbc_sinks WHERE id=?", (receipt,)).fetchone()
        require(sink is not None and sink["destination"] == name, "DELIVERY_DENIED")
        data = bytes(sink["bytes"])
        require(hashlib.sha256(data).hexdigest() == binding["digest"] == artifact["digest"], "DELIVERY_INTEGRITY")
        return row, data

    def collect_release(self, token, receipt):
        """One-shot delivery; queued bytes are reauthorized before leaving the service."""
        name = self._admin(token, "recipient")
        with self.transaction():
            row, data = self._delivery(name, receipt)
            require(row["mode"] == "pending", "DELIVERY_ALREADY_STARTED")
            self.db.execute("UPDATE tbc_delivery SET position=?,mode='done' WHERE id=?", (len(data), receipt))
            self.world.event("tbc_delivery", {"receipt": receipt, "bytes": len(data), "recipient": name})
            return data

    def collect_chunk(self, token, receipt, *, max_bytes=1024):
        """Pull exact approved bytes, rechecking revocation at each chunk boundary.

        This is staged artifact delivery, not live token generation or a network
        transport. A committed chunk cannot be recalled. Lost responses require
        application reconciliation: this method never silently retries bytes.
        """
        name = self._admin(token, "recipient")
        integer(max_bytes, 1)
        require(max_bytes <= 4096, "CHUNK_TOO_LARGE")
        with self.transaction():
            row, data = self._delivery(name, receipt)
            require(row["mode"] in {"pending", "stream"}, "DELIVERY_COMPLETE")
            start = row["position"]
            chunk = data[start:start + max_bytes]
            end = start + len(chunk)
            done = end == len(data)
            self.db.execute("UPDATE tbc_delivery SET position=?,mode=? WHERE id=?",
                            (end, "done" if done else "stream", receipt))
            self.world.event("tbc_delivery_chunk", {"receipt": receipt, "offset": start,
                                                   "bytes": len(chunk), "recipient": name})
            return {"bytes": chunk, "offset": start, "done": done}

    def emergency_stop(self, token, *, reason):
        """Durably disable local workload authority even when evidence storage fails.

        This does not kill OS processes. The control service and database must be
        outside the model's write authority. Recovery never revives old identities.
        """
        name = self._admin(token, "operator")
        require(isinstance(reason, str) and 0 < len(reason.strip()) <= 512, "REASON_REQUIRED")
        with self.transaction():
            self.db.execute("UPDATE tbc_supervision SET stopped=1 WHERE id=1")
            self.db.execute("UPDATE tbc_agents SET revoked=1")
            self.db.execute("UPDATE tbc_tasks SET state='QUARANTINED',epoch=epoch+1")
        try:
            with self.transaction():
                self.world.event("tbc_emergency_stop", {"operator": name, "reason_digest": digest(reason)})
        except (OSError, ValueError, sqlite3.Error):
            return {"stopped": True, "evidence_recorded": False}
        return {"stopped": True, "evidence_recorded": True}

    def resume_workload(self, token):
        name = self._admin(token, "operator")
        with self.transaction():
            require(self.db.execute("SELECT stopped FROM tbc_supervision WHERE id=1").fetchone()[0] == 1,
                    "NOT_STOPPED")
            self.world.event("tbc_workload_resumed", {"operator": name, "old_identities_revoked": True})
            self.db.execute("UPDATE tbc_supervision SET stopped=0 WHERE id=1")

    def _monitor_heads(self, task_id):
        # Snapshot reads are not task changes. Global revocation and source
        # invalidation still invalidate advice, regardless of task activity.
        task = self.db.execute("""SELECT head FROM evidence
            WHERE json_extract(body, '$.data.task')=?
            AND json_extract(body, '$.kind') != 'tbc_monitor_snapshot'
            ORDER BY seq DESC LIMIT 1""", (task_id,)).fetchone()
        control = self.db.execute("""SELECT head FROM evidence
            WHERE json_extract(body, '$.kind') IN
            ('tbc_source_invalidated', 'tbc_revoke', 'tbc_passport',
             'tbc_emergency_stop', 'tbc_workload_resumed')
            ORDER BY seq DESC LIMIT 1""").fetchone()
        return (task[0] if task else None, control[0] if control else None)

    def monitor_snapshot(self, token, task_id):
        """Bounded task metadata; other tasks cannot crowd out this history."""
        name = self._admin(token, "monitor")
        with self.transaction():
            task = self._task(task_id)
            allowed = sorted({"tbc_" + op for op in SCHEMAS} |
                             {"tbc_denied", "tbc_contract", "tbc_monitor_finding",
                              "tbc_blocked_attempt"})
            placeholders = ','.join('?' for _ in allowed)
            rows = self.db.execute(f"""SELECT seq,body FROM evidence
                WHERE json_extract(body, '$.data.task')=?
                AND json_extract(body, '$.kind') IN ({placeholders})
                ORDER BY seq DESC LIMIT 32""", (task_id, *allowed)).fetchall()
            events = [{"sequence": row["seq"], "kind": json.loads(row["body"])["kind"]}
                      for row in reversed(rows)]
            self.world.event("tbc_monitor_snapshot", {"task": task_id, "monitor": name})
            head, control_head = self._monitor_heads(task_id)
            body = {"task": task_id, "epoch": task["epoch"], "state": task["state"], "head": head,
                    "control_head": control_head, "monitor": name, "events": events,
                    "expires": min(self._now() + self.passport.lease_seconds, task["contract"].expires)}
            snapshot = self._put("monitor_snapshot", body)
            return {"snapshot": snapshot, **body}

    def apply_monitor_finding(self, token, raw):
        """AI advice can reduce authority, never grant it. Clear is only an observation."""
        name = self._admin(token, "monitor")
        q = parse_sdk_request(raw)
        require(set(q) == {"snapshot", "verdict", "reason"}, "INVALID_MONITOR_SCHEMA")
        require(all(isinstance(q[key], str) for key in q), "INVALID_MONITOR_SCHEMA")
        require(q["verdict"] in {"clear", "uncertain", "suspicious"}
                and q["reason"] in {"behavioral_anomaly", "possible_injection", "insufficient_evidence"},
                "INVALID_MONITOR_FINDING")
        with self.transaction():
            snapshot = self._get(q["snapshot"], "monitor_snapshot")
            task = self._task(snapshot["task"])
            head, control_head = self._monitor_heads(task["id"])
            require(snapshot["monitor"] == name and snapshot["epoch"] == task["epoch"]
                    and snapshot["head"] == head and snapshot.get("control_head") == control_head
                    and self._now() < snapshot["expires"], "STALE_MONITOR_EVIDENCE")
            require(self.db.execute("SELECT 1 FROM tbc_used WHERE id=?", (q["snapshot"],)).fetchone() is None,
                    "MONITOR_REPLAY")
            self.db.execute("INSERT INTO tbc_used VALUES(?)", (q["snapshot"],))
            state = task["state"]
            if q["verdict"] != "clear":
                target = "QUARANTINED" if q["verdict"] == "suspicious" else "READ_ONLY"
                if MODES[target] <= MODES[state]:
                    state = target
                self.db.execute("UPDATE tbc_tasks SET state=?,epoch=epoch+1 WHERE id=?", (state, task["id"]))
            self.world.event("tbc_monitor_finding", {"task": task["id"], "monitor": name,
                            "verdict": q["verdict"], "reason": q["reason"], "state": state})
            return {"state": state, "authority_granted": False}

    def restore(self, token, task_id):
        """Named human authority restores within the original hard ceiling; old leases stay invalid."""
        name = self._admin(token, "operator")
        with self.transaction():
            task = self._task(task_id)
            require(self.db.execute("SELECT body FROM tbc_config WHERE id=1").fetchone()[0]
                    == canonical(self.passport.to_dict()), "PASSPORT_DRIFT")
            self.db.execute("UPDATE tbc_tasks SET state='NORMAL',epoch=epoch+1,runtime_scope=? WHERE id=?",
                            (canonical(task["contract"].scope.to_dict()), task_id))
            self.world.event("tbc_restore", {"task": task_id, "operator": name, "fresh_lease_required": True})

    def census(self, token, task_id):
        self._admin(token, "operator")
        task = self._task(task_id)
        agents = []
        for row in self.db.execute("SELECT id,parent,model,zone,expires,revoked FROM tbc_agents WHERE task=?", (task_id,)):
            item = dict(row)
            try:
                self._agent(item["id"])
                item["active"] = True
            except AuthorityDenied:
                item["active"] = False
            agents.append(item)
        return {"task": task_id, "state": task["state"], "epoch": task["epoch"],
                "remaining": json.loads(task["remaining"]), "agents": agents}

    # -- Decision receipts ---------------------------------------------------
    # A receipt binds policy version, task epoch, source lineage, artifact
    # digest, recipient and outcome, so review never has to treat model
    # reasoning as proof. Receipts hold identifiers and digests, not record
    # text, and are readable only by operator or monitor authority.

    def _receipt_mac(self, body):
        return hmac.new(bytes.fromhex(self.world.meta("key")),
                        ("receipt" + body).encode(), hashlib.sha256).hexdigest()

    def _artifact_digest(self, result):
        if isinstance(result.get("digest"), str):
            return result["digest"]
        if isinstance(result.get("artifact"), str):
            with suppress(AuthorityDenied, ValueError, KeyError):
                return self._get(result["artifact"], "artifact")["digest"]
        return None

    def _record_receipt(self, task, agent, q, result, outcome, error=None):
        code = None
        if error is not None:
            code = error.args[0] if isinstance(error, AuthorityDenied) and error.args else type(error).__name__
            if not isinstance(code, str) or not code.isidentifier() or len(code) > 64:
                code = "DENIED"
        row = self.db.execute("SELECT sources FROM tbc_agents WHERE id=?", (agent["id"],)).fetchone()
        recipient = next((q[k] for k in ("destination", "recipient") if isinstance(q.get(k), str)), None)
        body = canonical({
            "policy_version": self.passport.policy_version,
            "passport_digest": digest(self.passport.to_dict()),
            "task": task["id"], "epoch": task["epoch"], "agent": agent["id"],
            "operation": q.get("op") if q.get("op") in {*SCHEMAS, "fan_in"} else None,
            "request_digest": digest(q) if q else None,
            "source_lineage": sorted(json.loads(row[0])) if row else [],
            "artifact_digest": self._artifact_digest(result),
            "recipient": recipient, "outcome": outcome, "code": code, "issued": self._now()})
        self.db.execute("INSERT INTO tbc_receipts(task,issued,body,mac) VALUES(?,?,?,?)",
                        (task["id"], self._now(), body, self._receipt_mac(body)))

    def decision_receipts(self, token, task_id, *, limit=64):
        """Integrity-checked receipts for one task, newest last."""
        self._admin_any(token, {"operator", "monitor"})
        integer(limit, 1)
        require(limit <= 1024, "RECEIPT_LIMIT")
        rows = self.db.execute("SELECT seq,body,mac FROM tbc_receipts WHERE task=? ORDER BY seq DESC LIMIT ?",
                               (task_id, limit)).fetchall()
        receipts = []
        for row in reversed(rows):
            require(hmac.compare_digest(self._receipt_mac(row["body"]), row["mac"]), "INTEGRITY_FAILURE")
            receipts.append({"sequence": row["seq"], **json.loads(row["body"])})
        return receipts

    def prune_receipts(self, token, *, older_than=None):
        """Apply the retention limit so the trail is not another store of student data."""
        name = self._admin(token, "operator")
        horizon = older_than if older_than is not None else self.receipt_retention_seconds
        require(horizon is not None, "RETENTION_NOT_CONFIGURED")
        integer(horizon, 1)
        with self.transaction():
            removed = self.db.execute("DELETE FROM tbc_receipts WHERE issued <= ?",
                                      (self._now() - horizon,)).rowcount
            self.world.event("tbc_receipts_pruned", {"operator": name, "removed": removed,
                                                     "horizon": horizon})
        return {"removed": removed}

    # -- Shared budget reservations -------------------------------------------
    # Parallel workers must not multiply resources. A trusted scheduler reserves
    # from the one task and workload balance before dispatch; completion settles
    # the actual use and returns the rest, cancellation returns everything, and
    # a reservation settles at most once.

    def reserve_budget(self, token, task_id, **amounts):
        name = self._admin(token, "operator")
        require(amounts and set(amounts) <= set(BUDGETS), "UNKNOWN_BUDGET")
        with self.transaction():
            task = self._task(task_id)
            require(task["state"] == "NORMAL", "RESERVATION_RESTRICTED")
            self._charge(task, **amounts)
            rid = secrets.token_hex(16)
            self.db.execute("INSERT INTO tbc_reservations VALUES(?,?,?,'held',?)",
                            (rid, task_id, canonical(amounts), name))
            self.world.event("tbc_reservation", {"task": task_id, "reservation": rid, "operator": name})
            return {"reservation": rid, "amounts": dict(amounts)}

    def _refund(self, task_id, amounts):
        current = json.loads(self.db.execute("SELECT remaining FROM tbc_tasks WHERE id=?", (task_id,)).fetchone()[0])
        workload = json.loads(self.db.execute("SELECT remaining FROM tbc_usage WHERE id=1").fetchone()[0])
        for key, amount in amounts.items():
            current[key] += amount
            workload[key] += amount
        self.db.execute("UPDATE tbc_usage SET remaining=? WHERE id=1", (canonical(workload),))
        self.db.execute("UPDATE tbc_tasks SET remaining=? WHERE id=?", (canonical(current), task_id))

    def _close_reservation(self, token, reservation, used, state):
        name = self._admin(token, "operator")
        with self.transaction():
            row = self.db.execute("SELECT * FROM tbc_reservations WHERE id=?", (reservation,)).fetchone()
            require(row is not None, "UNKNOWN_RESERVATION")
            require(row["state"] == "held", "RESERVATION_ALREADY_SETTLED")
            held = json.loads(row["amounts"])
            require(set(used) <= set(held), "UNKNOWN_BUDGET")
            for key, amount in used.items():
                require(integer(amount) <= held[key], "SETTLEMENT_EXCEEDS_RESERVATION")
            self._refund(row["task"], {key: held[key] - used.get(key, 0) for key in held})
            self.db.execute("UPDATE tbc_reservations SET state=? WHERE id=?", (state, reservation))
            self.world.event("tbc_reservation_" + state, {"task": row["task"], "reservation": reservation,
                                                          "operator": name})
            return {"reservation": reservation, "state": state,
                    "used": {key: used.get(key, 0) for key in held}}

    def settle_reservation(self, token, reservation, **used):
        return self._close_reservation(token, reservation, used, "settled")

    def cancel_reservation(self, token, reservation):
        return self._close_reservation(token, reservation, {}, "cancelled")

    # -- Declared task graph (P10) --------------------------------------------
    # Opt-in per task. Once declared, an agent may act only after a trusted gate
    # admits it as a node, and a message may cross only an admitted edge.
    # Replanning is another admission; nothing the model sends admits anything.

    def _graph_declared(self, task_id):
        return self.db.execute("SELECT 1 FROM tbc_graph_mode WHERE task=?", (task_id,)).fetchone() is not None

    def _require_admitted_node(self, task_id, agent_id):
        if self._graph_declared(task_id):
            require(self.db.execute("SELECT 1 FROM tbc_graph_nodes WHERE task=? AND agent=?",
                                    (task_id, agent_id)).fetchone() is not None, "NODE_NOT_ADMITTED")

    def _require_admitted_edge(self, task_id, source, target, channel):
        if self._graph_declared(task_id):
            require(self.db.execute("SELECT 1 FROM tbc_graph_edges WHERE task=? AND source=? AND target=? "
                                    "AND channel=?", (task_id, source, target, channel)).fetchone() is not None,
                    "AIRLOCK_CHANNEL_DENIED")

    def admit_graph(self, token, task_id, *, nodes=(), edges=()):
        """Declare the task graph, or admit a replanned change to it.

        ``edges`` are (source, target, channel) triples. Both endpoints must be
        admitted nodes of this task and the channel must be in both scopes.
        Admission never widens any agent's scope.
        """
        name = self._admin(token, "operator")
        nodes = [identifier(node) for node in nodes]
        edges = [tuple(identifier(part) for part in edge) for edge in edges]
        require(all(len(edge) == 3 for edge in edges), "INVALID_EDGE")
        with self.transaction():
            task = self._task(task_id)
            self.db.execute("INSERT OR IGNORE INTO tbc_graph_mode VALUES(?)", (task_id,))
            for node in nodes:
                agent, agent_task, _ = self._agent(node)
                require(agent_task["id"] == task["id"], "CROSS_TASK_ANCESTRY")
                self.db.execute("INSERT OR IGNORE INTO tbc_graph_nodes VALUES(?,?)", (task_id, node))
            for source, target, channel in edges:
                for endpoint in (source, target):
                    require(self.db.execute("SELECT 1 FROM tbc_graph_nodes WHERE task=? AND agent=?",
                                            (task_id, endpoint)).fetchone() is not None, "NODE_NOT_ADMITTED")
                require(channel in self._agent(source)[2].channels and channel in self._agent(target)[2].channels,
                        "AIRLOCK_CHANNEL_DENIED")
                self.db.execute("INSERT OR IGNORE INTO tbc_graph_edges VALUES(?,?,?,?)",
                                (task_id, source, target, channel))
            self.world.event("tbc_graph_admitted", {"task": task_id, "operator": name,
                                                    "nodes": len(nodes), "edges": len(edges)})
            return self.task_graph(token, task_id)

    def task_graph(self, token, task_id):
        self._admin_any(token, {"operator", "monitor"})
        return {"task": task_id, "declared": self._graph_declared(task_id),
                "nodes": [r[0] for r in self.db.execute(
                    "SELECT agent FROM tbc_graph_nodes WHERE task=? ORDER BY agent", (task_id,))],
                "edges": [list(r) for r in self.db.execute(
                    "SELECT source,target,channel FROM tbc_graph_edges WHERE task=? ORDER BY 1,2,3", (task_id,))]}

    # -- Fan-in gate -------------------------------------------------------------
    # Before a coordinator accepts a worker's result, a trusted gate checks
    # provenance (who produced it, under a valid authority), artifact identity
    # (MAC and the exact expected digest), the current epoch, inherited labels
    # and the intended destination. Agreement among agents is not a credential.

    def accept_result(self, token, artifact, *, coordinator, expected_digest, destination):
        name = self._admin(token, "operator")
        with self.transaction():
            a = self._get(artifact, "artifact")
            require(isinstance(expected_digest, str) and hmac.compare_digest(a["digest"], expected_digest),
                    "ARTIFACT_IDENTITY_MISMATCH")
            target, task, scope = self._agent(coordinator)
            require(a["task"] == task["id"], "ARTIFACT_SCOPE_DENIED")
            producer = a.get("producer")
            require(isinstance(producer, str) and producer in a["audience"], "PROVENANCE_REQUIRED")
            _, producer_task, _ = self._agent(producer)
            require(producer_task["id"] == task["id"], "CROSS_TASK_ANCESTRY")
            require(a.get("epoch") == task["epoch"], "STALE_RESULT")
            if self._graph_declared(task["id"]):
                require(self.db.execute("SELECT 1 FROM tbc_graph_edges WHERE task=? AND source=? AND target=?",
                                        (task["id"], producer, target["id"])).fetchone() is not None,
                        "AIRLOCK_CHANNEL_DENIED")
            require(set(a["labels"]) <= scope.data_classes, "DATA_RIGHTS_DENIED")
            self._source_valid(a["sources"], scope)
            require(destination in scope.destinations, "DESTINATION_DENIED")
            require(not (a["labels"] and destination == "public"), "PROHIBITED_FLOW")
            accepted = self._put("artifact", {**a, "audience": [target["id"]]})
            self._taint(target, a["labels"], a["sources"])
            self._record_receipt(task, target, {"op": "fan_in", "destination": destination},
                                 {"digest": a["digest"]}, "ACCEPTED")
            self.world.event("tbc_fan_in_accepted", {"task": task["id"], "producer": producer,
                                                     "coordinator": target["id"], "operator": name,
                                                     "digest": a["digest"]})
            return {"artifact": accepted, "digest": a["digest"]}

    # -- Freshness ----------------------------------------------------------------
    # A fresh check alone leaves a check-then-act race. An adapter that commits
    # outside this transaction presents a freshness proof and rejects it when the
    # task epoch moved, the task stopped, or the proof is older than max_age.
    # A partitioned worker that cannot obtain one must stop.

    def issue_freshness(self, token, task_id):
        self._admin(token, "operator")
        with self.transaction():
            task = self._task(task_id)
            issued = self._now()
            proof = self._put("freshness", {"task": task_id, "epoch": task["epoch"], "issued": issued})
            return {"proof": proof, "epoch": task["epoch"], "issued": issued}

    def check_freshness(self, proof, *, max_age):
        integer(max_age, 1)
        try:
            p = self._get(proof, "freshness")
            task = self._task(p["task"])
        except AuthorityDenied as error:
            raise AuthorityDenied("FRESHNESS_UNPROVEN") from error
        require(task["epoch"] == p["epoch"] and task["state"] != "QUARANTINED"
                and 0 <= self._now() - p["issued"] <= max_age, "FRESHNESS_UNPROVEN")
        return {"task": p["task"], "epoch": p["epoch"]}

    def manual_queue(self, token):
        """Work deferred by the minimum review time, for the named manual route."""
        self._admin_any(token, {"operator", "reviewer"})
        return [dict(row) for row in self.db.execute("SELECT * FROM tbc_manual_queue ORDER BY queued")]



class Guardian:
    """Authority-asymmetric assurance API: no grant or restoration method.

    Invoke evaluate on trusted configuration/runtime events. It also runs at the
    model dispatch boundary via the stored configuration check. A scheduler or
    event bus must invoke graph checks when managing external infrastructure.
    """

    def __init__(self, runtime: TrustRuntime):
        self._runtime = runtime

    def contract(self, task_id, state, *, scope=None, reason="assurance_loss"):
        r = self._runtime
        require(state in MODES, "UNKNOWN_GUARDIAN_STATE")
        with r.transaction():
            task = r._task(task_id)
            require(MODES[state] <= MODES[task["state"]], "GUARDIAN_CANNOT_EXPAND")
            current = Scope.parse(json.loads(task["runtime_scope"]))
            narrowed = current if scope is None else scope
            require(narrowed.subset(current), "GUARDIAN_CANNOT_EXPAND")
            r.db.execute("UPDATE tbc_tasks SET state=?,epoch=epoch+1,runtime_scope=? WHERE id=?",
                         (state, canonical(narrowed.to_dict()), task_id))
            r.world.event("tbc_contract", {"task": task_id, "state": state, "reason_digest": digest(reason)})

    def revoke(self, agent_id):
        r = self._runtime
        with r.transaction():
            require(r.db.execute("SELECT 1 FROM tbc_agents WHERE id=?", (agent_id,)).fetchone(), "UNKNOWN_AGENT")
            r.db.execute("UPDATE tbc_agents SET revoked=1 WHERE id=?", (agent_id,))
            r.world.event("tbc_revoke", {"agent": agent_id})

    def revoke_task(self, task_id, *, reason="revocation"):
        """Raise the task epoch so queued work, stale leases and later release chunks fail.

        Agents stay enrolled and must obtain fresh leases; information already
        disclosed cannot be recalled. This contracts authority and grants none.
        """
        r = self._runtime
        with r.transaction():
            r._task(task_id)
            r.db.execute("UPDATE tbc_tasks SET epoch=epoch+1 WHERE id=?", (task_id,))
            r.world.event("tbc_revoke", {"task": task_id, "epoch_raised": True,
                                         "reason_digest": digest(reason)})

    def evaluate(self, task_id):
        """Return concrete source-to-sink counterexample paths and quarantine on violation."""
        with self._runtime.transaction():
            return self._evaluate_locked(task_id)

    def _evaluate_locked(self, task_id):
        r = self._runtime
        task = r._task(task_id)
        violations = []
        if r.db.execute("SELECT body FROM tbc_config WHERE id=1").fetchone()[0] != canonical(r.passport.to_dict()):
            violations.append({"invariant": "passport_drift", "path": []})
        nodes = {}
        for row in r.db.execute("SELECT id FROM tbc_agents WHERE task=?", (task_id,)):
            try:
                a, _, scope = r._agent(row[0])
                nodes[a["id"]] = (a, scope)
            except AuthorityDenied:
                continue
        edges = {}
        for row in r.db.execute("SELECT source,target FROM tbc_edges WHERE task=?", (task_id,)):
            if row["source"] in nodes and row["target"] in nodes:
                edges.setdefault(row["source"], set()).add(row["target"])
        for source, (a, scope) in nodes.items():
            if not (json.loads(a["labels"]) or (scope.data_classes and "request_context" in scope.operations)):
                continue
            queue, seen = [(source, [source])], set()
            while queue:
                node, path = queue.pop(0)
                if node in seen:
                    continue
                seen.add(node)
                if "public" in nodes[node][1].destinations and "release_artifact" in nodes[node][1].operations:
                    violations.append({"invariant": "restricted_to_public", "path": path})
                queue.extend((target, [*path, target]) for target in sorted(edges.get(node, ())))
        if violations:
            r.db.execute("UPDATE tbc_tasks SET state='QUARANTINED',epoch=epoch+1 WHERE id=?", (task_id,))
        r.world.event("tbc_invariants", {"task": task_id, "violations": violations})
        return {"task": task_id, "state": "QUARANTINED" if violations else task["state"],
                "counterexamples": violations, "nodes": len(nodes)}
