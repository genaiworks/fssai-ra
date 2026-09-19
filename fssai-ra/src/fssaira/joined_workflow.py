"""Durable, offline joined reference workflow. Synthetic credentials; no code sandbox.

Only dispatch() is an untrusted JSON interface. Constructor, DB and administrative
credentials belong to the trusted host. No network/tool/code/stream adapters exist.
SQLite serializes authorization, budget consumption, effects, release and evidence.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def strict_json(raw):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("DUPLICATE_FIELD")
            out[key] = value
        return out
    if len(raw.encode()) > 16384:
        raise ValueError("REQUEST_TOO_LARGE")
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE")))
    pending = [(value, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > 64:
            raise ValueError("REQUEST_TOO_DEEP")
        if isinstance(item, dict):
            pending.extend((v, depth + 1) for v in item.values())
        elif isinstance(item, list):
            pending.extend((v, depth + 1) for v in item)
    return value


class Denied(Exception):
    pass


# Published synthetic credentials, deliberately unsuitable for institutional use.
TOKENS = {"demo-advisor": ("advisor", "advisor"), "demo-instructor": ("instructor", "instructor"),
          "demo-registrar": ("registrar", "registrar"), "demo-appeal": ("appeal", "appeal"),
          "demo-recipient": ("recipient", "recipient"), "demo-admin": ("admin", "admin")}
PACKS = {
    "education": {"operation": "correct_transcript", "before": "C", "supported": "B", "wrong": "A"},
    "benefits": {"operation": "correct_eligibility", "before": "pending", "supported": "eligible",
                 "wrong": "ineligible"},
}


class Workflow:
    def __init__(self, path, *, pack="education", profile="teaching", control=True, mediator="legacy"):
        if mediator not in ("legacy", "tbc"):
            raise ValueError("UNKNOWN_MEDIATOR")
        if profile != "teaching":
            raise ValueError("NOT_QUALIFIED_FOR_OPERATIONAL_USE")
        if pack not in PACKS:
            raise ValueError("UNKNOWN_PACK")
        self.path, self.control, self.pack = str(path), control, PACKS[pack]
        self.db = sqlite3.connect(self.path, isolation_level=None, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS records(tenant TEXT, subject TEXT, value TEXT, version INTEGER,
          source_value TEXT, source_version INTEGER, consent INTEGER, PRIMARY KEY(tenant,subject));
        CREATE TABLE IF NOT EXISTS grants(id TEXT PRIMARY KEY, holder TEXT, parent TEXT, root TEXT,
          tenant TEXT, subject TEXT, beneficiary TEXT, purpose TEXT, operations TEXT, remaining INTEGER,
          revoked INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS objects(id TEXT PRIMARY KEY, kind TEXT, body TEXT);
        CREATE TABLE IF NOT EXISTS effects(id TEXT PRIMARY KEY, proposal TEXT, value TEXT, version INTEGER);
        CREATE TABLE IF NOT EXISTS sinks(id INTEGER PRIMARY KEY, recipient TEXT, bytes BLOB, proposal TEXT);
        CREATE TABLE IF NOT EXISTS evidence(seq INTEGER PRIMARY KEY, previous TEXT, body TEXT, head TEXT);
        ''')
        self.db.execute("BEGIN IMMEDIATE")
        if not self.db.execute("SELECT 1 FROM meta WHERE k='pack'").fetchone():
            for k, v in {"pack": pack, "policy": "1", "recipient_version": "1", "clock": "0",
                         "key": secrets.token_hex(32)}.items():
                self.db.execute("INSERT INTO meta VALUES(?,?)", (k, v))
            for tenant, subject in [("campus", "s1"), ("campus", "s2"), ("other", "s1")]:
                self.db.execute("INSERT INTO records VALUES(?,?,?,?,?,?,?)",
                                (tenant, subject, self.pack["before"], 1, self.pack["supported"], 1, 1))
            self.db.execute("INSERT INTO grants VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            ("root", "advisor", "", "root", "campus", "s1", "s1", "correction",
                             canonical(["read", "propose", "execute", "release", "delegate"]), 20, 0))
            self.event("seed", {"pack": pack, "synthetic": True})
        elif self.meta("pack") != pack:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise ValueError("PACK_MISMATCH")
        stored_mediator = self.db.execute("SELECT v FROM meta WHERE k='mediator'").fetchone()
        if stored_mediator and stored_mediator[0] != mediator:
            self.db.execute("ROLLBACK")
            self.db.close()
            raise ValueError("MEDIATOR_MISMATCH")
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('mediator',?)", (mediator,))
        # Add an authorization epoch to older teaching stores. Older contexts lack
        # the binding and are intentionally invalidated rather than silently upgraded.
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('consent_version','1')")
        self.db.execute("COMMIT")

    def close(self):
        self.db.close()

    def meta(self, key):
        return self.db.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()[0]

    def event(self, kind, data):
        last = self.db.execute("SELECT head FROM evidence ORDER BY seq DESC LIMIT 1").fetchone()
        previous = last[0] if last else "0" * 64
        body = canonical({"kind": kind, "data": data})
        head = hmac.new(bytes.fromhex(self.meta("key")), (previous + body).encode(), hashlib.sha256).hexdigest()
        self.db.execute("INSERT INTO evidence(previous,body,head) VALUES(?,?,?)", (previous, body, head))
        return head

    def put(self, kind, body):
        oid = secrets.token_hex(16)
        self.db.execute("INSERT INTO objects VALUES(?,?,?)", (oid, kind, canonical(body)))
        return oid

    def get(self, oid, kind):
        row = self.db.execute("SELECT body FROM objects WHERE id=? AND kind=?", (oid, kind)).fetchone()
        if not row:
            raise Denied("UNKNOWN_REFERENCE")
        return json.loads(row[0])

    def record(self, tenant, subject):
        row = self.db.execute("SELECT * FROM records WHERE tenant=? AND subject=?", (tenant, subject)).fetchone()
        if not row:
            raise Denied("UNKNOWN_SUBJECT")
        return dict(row)

    def grant(self, gid, actor, operation, tenant="campus", subject="s1"):
        seen, chain = set(), []
        while gid:
            if gid in seen or len(seen) >= 5:
                raise Denied("DELEGATION_CYCLE_OR_DEPTH")
            seen.add(gid)
            row = self.db.execute("SELECT * FROM grants WHERE id=?", (gid,)).fetchone()
            if not row:
                raise Denied("UNKNOWN_GRANT")
            g = dict(row)
            if (g["revoked"] or g["remaining"] <= 0 or g["tenant"] != tenant or
                    g["subject"] != subject or g["beneficiary"] != subject or
                    g["purpose"] != "correction" or operation not in json.loads(g["operations"])):
                raise Denied("GRANT_SCOPE_OR_REVOKED")
            if not chain and g["holder"] != actor:
                raise Denied("WRONG_HOLDER")
            chain.append(g)
            gid = g["parent"]
        if not chain or chain[-1]["id"] != chain[0]["root"]:
            raise Denied("UNROOTED")
        for g in chain:
            self.db.execute("UPDATE grants SET remaining=remaining-1 WHERE id=?", (g["id"],))
        return chain[0]

    def current_authority(self, context):
        r = self.record(context["tenant"], context["subject"])
        if (not r["consent"] or
                context.get("consent_version") != self.meta("consent_version") or
                self.meta("policy") != context["policy"] or
                self.meta("recipient_version") != context["recipient_version"] or
                int(self.meta("clock")) > context["expires"]):
            raise Denied("STALE_AUTHORITY")
        return r

    def current(self, context):
        r = self.current_authority(context)
        if (r["version"] != context["version"] or
                r["source_version"] != context["source_version"] or
                self.meta("policy") != context["policy"] or
                self.meta("recipient_version") != context["recipient_version"] or
                int(self.meta("clock")) > context["expires"]):
            raise Denied("STALE_CONTEXT")
        return r

    def dispatch(self, token, raw):
        try:
            identity = next((v for k, v in TOKENS.items() if hmac.compare_digest(k, token)), None)
            # Delegated identities use an out-of-band synthetic token convention, not request fields.
            if identity is None and token in ("demo-child1", "demo-child2"):
                identity = (token.removeprefix("demo-"), "advisor")
            if identity is None:
                raise Denied("AUTHENTICATION_REQUIRED")
            request = strict_json(raw)
            if not isinstance(request, dict):
                raise Denied("OBJECT_REQUIRED")
            self.db.execute("BEGIN IMMEDIATE")
            result = self.handle(*identity, request)
            self.db.execute("COMMIT")
            return {"ok": True, **result}
        except (Denied, ValueError, KeyError, TypeError, RecursionError, sqlite3.Error):
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            # Never echo untrusted values, exception messages or synthetic rationales.
            return {"ok": False, "code": "DENIED"}

    def handle(self, actor, role, q):
        schemas = {
            "read": {"op", "tenant", "subject", "grant"},
            "propose": {"op", "context", "value", "operation", "recipient", "rationale"},
            "confirm": {"op", "proposal"}, "approve": {"op", "proposal", "confirmation"},
            "execute": {"op", "proposal", "approval"}, "release": {"op", "proposal"},
            "reconcile": {"op", "proposal"}, "appeal": {"op", "proposal", "value"},
            "delegate": {"op", "grant", "holder", "operations", "budget"},
            "revoke": {"op", "grant"}, "change": {"op", "kind", "value"},
        }
        op = q.get("op")
        if op not in schemas or set(q) - schemas[op]:
            raise Denied("UNSUPPORTED_INTERFACE_OR_FIELD")
        if op == "read":
            tenant, subject, gid = q.get("tenant", "campus"), q.get("subject", "s1"), q.get("grant", "root")
            self.grant(gid, actor, "read", tenant, subject)
            r = self.record(tenant, subject)
            if not r["consent"]:
                raise Denied("CONSENT_REVOKED")
            c = {"tenant": tenant, "subject": subject, "actor": actor, "grant": gid,
                 "version": r["version"], "source_version": r["source_version"], "policy": self.meta("policy"),
                 "recipient_version": self.meta("recipient_version"),
                 "consent_version": self.meta("consent_version"), "expires": int(self.meta("clock")) + 100,
                 "value": r["value"], "supported": r["source_value"], "purpose": "correction"}
            cid = self.put("context", c)
            self.event("context", {"context": cid, "digest": digest(c), "actor": actor})
            return {"context": cid, "value": r["value"], "supported": r["source_value"],
                    "label": "synthetic-academic", "model": "offline-scripted"}
        if op == "delegate":
            parent = self.grant(q.get("grant", "root"), actor, "delegate")
            operations = q["operations"]
            budget = q["budget"]
            if (not isinstance(operations, list) or not set(operations) <= set(json.loads(parent["operations"]))
                    or type(budget) is not int or not 0 < budget <= parent["remaining"]
                    or q["holder"] not in ("child1", "child2")):
                raise Denied("DELEGATION_AMPLIFICATION")
            gid = secrets.token_hex(16)
            self.db.execute("INSERT INTO grants VALUES(?,?,?,?,?,?,?,?,?,?,0)",
                            (gid, q["holder"], parent["id"], parent["root"], parent["tenant"], parent["subject"],
                             parent["beneficiary"], parent["purpose"], canonical(operations), budget))
            self.event("delegation", {"grant": gid, "parent": parent["id"]})
            return {"grant": gid}
        if op in ("change", "revoke"):
            if role != "admin":
                raise Denied("ADMIN_REQUIRED")
            if op == "revoke":
                self.db.execute("UPDATE grants SET revoked=1 WHERE id=?", (q["grant"],))
            elif q["kind"] in ("policy", "recipient_version", "clock"):
                old = int(self.meta(q["kind"]))
                if type(q["value"]) is not int or q["value"] <= old:
                    raise Denied("MONOTONIC_VERSION_REQUIRED")
                self.db.execute("UPDATE meta SET v=? WHERE k=?", (str(q["value"]), q["kind"]))
            elif q["kind"] == "consent":
                if type(q["value"]) is not int or q["value"] not in (0, 1):
                    raise Denied("INVALID_CONSENT")
                self.db.execute("UPDATE records SET consent=? WHERE tenant='campus' AND subject='s1'", (q["value"],))
                self.db.execute("UPDATE meta SET v=CAST(v AS INTEGER)+1 WHERE k='consent_version'")
            elif q["kind"] == "source":
                if q["value"] not in (self.pack["before"], self.pack["supported"], self.pack["wrong"]):
                    raise Denied("UNKNOWN_VALUE")
                self.db.execute("UPDATE records SET source_value=?,source_version=source_version+1 "
                                "WHERE tenant='campus' AND subject='s1'", (q["value"],))
            else:
                raise Denied("UNKNOWN_CHANGE")
            self.event(op, {"actor": actor, "request_digest": digest(q)})
            return {}
        if op == "propose":
            c = self.get(q["context"], "context")
            self.grant(c["grant"], actor, "propose", c["tenant"], c["subject"])
            self.current(c)
            if c["actor"] != actor or q["operation"] != self.pack["operation"] or q["recipient"] != "recipient":
                raise Denied("COMPOSITION_SCOPE")
            if q["value"] not in (self.pack["before"], self.pack["supported"], self.pack["wrong"]):
                raise Denied("INVALID_VALUE")
            # Rationale is explicitly discarded: never evidence, authority, release bytes, or telemetry.
            p = {"context": q["context"], "binding": c, "value": q["value"], "operation": q["operation"],
                 "recipient": q["recipient"]}
            pid = self.put("proposal", p)
            self.event("proposal", {"proposal": pid, "digest": digest(p)})
            return {"proposal": pid, "digest": digest(p)}
        p = self.get(q["proposal"], "proposal")
        c = p["binding"]
        if op == "confirm":
            if role != "instructor":
                raise Denied("INSTRUCTOR_REQUIRED")
            r = self.current(c)
            if self.control and r["source_value"] != p["value"]:
                raise Denied("UNSUPPORTED_PROPOSAL")
            cid = self.put("confirmation", {"proposal_digest": digest(p), "actor": actor,
                                             "source_version": r["source_version"]})
            self.event("confirmation", {"confirmation": cid, "proposal": q["proposal"]})
            return {"confirmation": cid}
        if op == "approve":
            if role != "registrar":
                raise Denied("REGISTRAR_REQUIRED")
            self.current(c)
            confirmation = self.get(q["confirmation"], "confirmation")
            if confirmation["proposal_digest"] != digest(p) or confirmation["actor"] == actor:
                raise Denied("EXACT_CONFIRMATION_REQUIRED")
            aid = self.put("approval", {"proposal_digest": digest(p), "confirmation": q["confirmation"],
                                        "actor": actor})
            self.event("approval", {"approval": aid, "proposal": q["proposal"]})
            return {"approval": aid}
        if op == "reconcile":
            if actor != c["actor"] and role not in ("registrar", "appeal"):
                raise Denied("RECONCILIATION_SCOPE")
            if actor == c["actor"]:
                self.grant(c["grant"], actor, "execute", c["tenant"], c["subject"])
                self.current_authority(c)
            e = self.db.execute("SELECT value,version FROM effects WHERE id=?", (q["proposal"],)).fetchone()
            return {"state": "committed" if e else "not_dispatched", "effect": dict(e) if e else None}
        if op == "execute":
            approval = self.get(q["approval"], "approval")
            if approval["proposal_digest"] != digest(p) or actor != c["actor"]:
                raise Denied("EXACT_APPROVAL_REQUIRED")
            self.grant(c["grant"], actor, "execute", c["tenant"], c["subject"])
            old = self.db.execute("SELECT * FROM effects WHERE id=?", (q["proposal"],)).fetchone()
            if old:
                self.current_authority(c)
                return {"state": "committed", "replayed": True, "version": old["version"]}
            r = self.current(c)
            self.db.execute("UPDATE records SET value=?,version=version+1 WHERE tenant=? AND subject=?",
                            (p["value"], c["tenant"], c["subject"]))
            self.db.execute("INSERT INTO effects VALUES(?,?,?,?)",
                            (q["proposal"], digest(p), p["value"], r["version"] + 1))
            head = self.event("effect", {"proposal": q["proposal"], "digest": digest(p),
                                         "approval": q["approval"], "version": r["version"] + 1})
            return {"state": "committed", "replayed": False, "receipt": head, "version": r["version"] + 1}
        if op == "release":
            if actor != p["recipient"]:
                raise Denied("RECIPIENT_REQUIRED")
            self.grant(c["grant"], c["actor"], "release", c["tenant"], c["subject"])
            # Release is an independently authenticated action over fixed server-rendered bytes.
            self.current({**c, "version": c["version"] + 1})
            effect = self.db.execute("SELECT 1 FROM effects WHERE id=?", (q["proposal"],)).fetchone()
            if not effect:
                raise Denied("NO_EFFECT")
            content = canonical({"subject": c["subject"], "value": p["value"], "proposal": q["proposal"]}).encode()
            self.db.execute("INSERT INTO sinks(recipient,bytes,proposal) VALUES(?,?,?)", (actor, content, q["proposal"]))
            head = self.event("release", {"proposal": q["proposal"], "recipient": actor,
                                          "bytes_digest": hashlib.sha256(content).hexdigest()})
            return {"bytes": content.decode(), "receipt": head}
        if op == "appeal":
            if role != "appeal" or q["value"] not in (self.pack["before"], self.pack["supported"]):
                raise Denied("INDEPENDENT_APPEAL_REQUIRED")
            effect = self.db.execute("SELECT version FROM effects WHERE id=?", (q["proposal"],)).fetchone()
            r = self.record(c["tenant"], c["subject"])
            if not effect or effect[0] != r["version"]:
                raise Denied("STALE_APPEAL")
            self.db.execute("UPDATE records SET value=?,version=version+1 WHERE tenant=? AND subject=?",
                            (q["value"], c["tenant"], c["subject"]))
            head = self.event("appeal_correction", {"proposal": q["proposal"], "actor": actor,
                                                    "value": q["value"], "prior_version": r["version"]})
            return {"receipt": head, "version": r["version"] + 1}
        raise Denied("UNKNOWN_OPERATION")

    def checkpoint(self):
        row = self.db.execute("SELECT seq,head FROM evidence ORDER BY seq DESC LIMIT 1").fetchone()
        return dict(row)

    def verify(self, witness):
        if (not isinstance(witness, dict) or set(witness) != {"seq", "head"} or
                type(witness["seq"]) is not int or witness["seq"] < 1 or
                not isinstance(witness["head"], str) or len(witness["head"]) != 64):
            return False
        previous, sequence, witnessed = "0" * 64, 0, False
        for row in self.db.execute("SELECT * FROM evidence ORDER BY seq"):
            head = hmac.new(bytes.fromhex(self.meta("key")), (previous + row["body"]).encode(), hashlib.sha256).hexdigest()
            if row["seq"] != sequence + 1 or row["previous"] != previous or row["head"] != head:
                return False
            previous, sequence = head, row["seq"]
            if sequence == witness["seq"]:
                if not hmac.compare_digest(head, witness["head"]):
                    return False
                witnessed = True
        return witnessed


def call(world, token="demo-advisor", **request):
    return world.dispatch(token, canonical(request))
