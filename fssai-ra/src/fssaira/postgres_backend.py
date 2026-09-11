"""PostgreSQL profile: the durable, transactional reference deployment.

Postgres is the recommended system of record for an institutional pilot, for one
reason that matters more than performance: it lets the authoritative resource
state and the tamper-evident decision record share a transaction. That turns the
architecture's weakest documented link -- "the mutation landed but its outcome
evidence did not" -- from a recoverable incident into an impossible state.

Everything here is a thin binding over :mod:`fssaira.sql_backend`, which is
dialect-agnostic. The same code runs on SQLite in continuous integration, so the
atomicity property is *tested on every commit* rather than asserted only for a
database that CI cannot start.

Operational notes for a deployment
----------------------------------
* Give the control plane a role that can ``INSERT`` into ``fssaira.evidence``
  and has no ``UPDATE`` or ``DELETE`` on it. Append-only should be enforced by
  the database grant, not only by application code. :func:`append_only_grants`
  emits the statements.
* Run the evidence table on storage with point-in-time recovery. Hash chaining
  detects truncation; it does not undo it.
* Separate the database administrator from the service owner. A DBA who can
  rewrite the chain and the application that writes it should not be the same
  person -- see ``docs/SECURITY.md``.
"""
from __future__ import annotations

import os

from .atomic_execution import AtomicExecutor, sql_evidence, sql_object_store, sql_register
from .sql_backend import POSTGRES, SqlDatabase, open_postgres, schema_statements

DEFAULT_DSN = "postgresql://fssaira:fssaira@localhost:5432/fssaira"


def database_from_env(url: str | None = None, schema: str | None = None,
                      *, evidence_token: str | None = None) -> SqlDatabase:
    """Open the configured SQL profile.

    ``FSSAI_DATABASE_URL`` selects the dialect: a ``postgresql://`` URL uses
    Postgres, ``sqlite:///path`` (or a bare path) uses SQLite. SQLite is
    supported deliberately -- a single-institution pilot on one machine is a
    legitimate deployment, and it should not have to pretend to be a cluster.
    """
    from .sql_backend import open_sqlite

    dsn = url or os.getenv("FSSAI_DATABASE_URL", "")
    namespace = schema or os.getenv("FSSAI_DATABASE_SCHEMA", "fssaira")
    if not dsn:
        raise ValueError("no database URL configured (set FSSAI_DATABASE_URL)")
    token = evidence_token or os.getenv("FSSAI_EVIDENCE_TOKEN") or None
    if dsn.startswith("sqlite://"):
        path = dsn.replace("sqlite:///", "").replace("sqlite://", "") or ":memory:"
        return open_sqlite(path, namespace, evidence_token=token)
    if dsn.startswith(("postgres://", "postgresql://")):
        return open_postgres(dsn, namespace, evidence_token=token)
    return open_sqlite(dsn, namespace, evidence_token=token)


def PostgresCaseRegister(dsn: str, *, schema: str = "fssaira"):
    """Register port backed by Postgres."""
    return sql_register(open_postgres(dsn, schema))


def PostgresEvidenceLedger(dsn: str, append_token: str = "", *, schema: str = "fssaira"):
    """Evidence port backed by Postgres. Append-only by grant and by code."""
    return sql_evidence(open_postgres(dsn, schema, evidence_token=append_token or None))


def PostgresObjectStore(dsn: str, *, schema: str = "fssaira"):
    """Object store for proposals, approvals, and receipts."""
    return sql_object_store(open_postgres(dsn, schema))


def build_atomic_executor(profile, database: SqlDatabase, evidence_token: str,
                          *, approval_keys: dict[str, str] | None = None) -> AtomicExecutor:
    """Compile a validated application profile into a transactional executor."""
    return AtomicExecutor(
        database,
        evidence_token,
        approval_keys=approval_keys,
        allowed_operations=profile.allowed_operations,
        transition_rules=profile.transition_rules,
        required_approval_roles=profile.required_approval_roles,
    )


def ddl(schema: str = "fssaira") -> str:
    """The full schema as one script, for review by a database administrator."""
    return ";\n\n".join(schema_statements(POSTGRES, schema)) + ";\n"


def append_only_grants(role: str, schema: str = "fssaira") -> str:
    """Grants that make the evidence table append-only at the database level.

    Application-level append-only is a promise. A revoked ``UPDATE`` privilege
    is a control. Institutions that need the stronger claim should apply these
    and record the result in their own assurance matrix.
    """
    return "\n".join([
        f"GRANT USAGE ON SCHEMA {schema} TO {role};",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {schema}.resources TO {role};",
        f"GRANT SELECT, INSERT ON {schema}.execution_results TO {role};",
        f"GRANT SELECT, INSERT ON {schema}.evidence TO {role};",
        f"REVOKE UPDATE, DELETE ON {schema}.evidence FROM {role};",
        f"GRANT SELECT, INSERT, UPDATE ON {schema}.objects TO {role};",
        f"GRANT SELECT, INSERT ON {schema}.approval_uses TO {role};",
        f"GRANT SELECT, INSERT, UPDATE, DELETE ON {schema}.pending_outcomes TO {role};",
        f"GRANT SELECT, INSERT, UPDATE ON {schema}.counters TO {role};",
    ]) + "\n"


__all__ = [
    "DEFAULT_DSN", "PostgresCaseRegister", "PostgresEvidenceLedger", "PostgresObjectStore",
    "append_only_grants", "build_atomic_executor", "database_from_env", "ddl",
]
