"""Durable state for key custody and encrypted records.

Why this module exists
----------------------
:class:`~fssaira.key_custody.KeyCustody` and
:class:`~fssaira.encrypted_records.EncryptedRecordSource` kept everything in
process memory. A restart lost every wrapped data key, so every stored ciphertext
became unreadable, and lost the erasure journal, so nothing proved which subjects
had been erased.

This module persists exactly what custody needs to survive a restart:

* wrapped data keys (each already encrypted under its class key),
* the current key-encryption-key generation per data class,
* the erasure journal and the set of destroyed subjects,
* encrypted field rows (nonce and ciphertext only).

It does **not** persist the master key. Key-encryption keys are derived from a
master key that :func:`load_master_key` reads from a secret file, which must not
live in this database. Whoever holds the database alone holds only ciphertext and
wrapped keys. Put the custody database on a different server, with different
administrators, from the application database where you can.

Each custody change that touches more than one row (erasure, rotation, restore)
commits in one transaction. This is still software custody: it is not an HSM and
does not stop an administrator who holds both the database and the master key.
"""
from __future__ import annotations

import contextlib
import os
import stat
from pathlib import Path

from .key_custody import Ciphertext, ErasureEntry, WrappedKey
from .sql_backend import SQLITE, SqlDatabase, open_postgres, open_sqlite


def _real(dialect) -> str:
    return "REAL" if dialect is SQLITE else "DOUBLE PRECISION"


def custody_schema(database: SqlDatabase) -> list[str]:
    d = database.dialect
    t = database.table
    statements = [] if d is SQLITE else [f"CREATE SCHEMA IF NOT EXISTS {database.schema}"]
    return statements + [
        f"""CREATE TABLE IF NOT EXISTS {t('custody_kek_generations')} (
                data_class {d.text_type} PRIMARY KEY,
                generation {d.big_int} NOT NULL
            )""",
        f"""CREATE TABLE IF NOT EXISTS {t('custody_wrapped_keys')} (
                subject        {d.text_type} NOT NULL,
                data_class     {d.text_type} NOT NULL,
                kek_generation {d.big_int} NOT NULL,
                key_generation {d.big_int} NOT NULL,
                nonce_hex      {d.text_type} NOT NULL,
                body_hex       {d.text_type} NOT NULL,
                PRIMARY KEY (subject, data_class)
            )""",
        f"""CREATE TABLE IF NOT EXISTS {t('custody_erasures')} (
                seq       {d.big_int} PRIMARY KEY,
                subject   {d.text_type} NOT NULL,
                erased_at {_real(d)} NOT NULL,
                erased_by {d.text_type} NOT NULL,
                reason    {d.text_type} NOT NULL
            )""",
        f"""CREATE TABLE IF NOT EXISTS {t('custody_destroyed')} (
                subject {d.text_type} PRIMARY KEY
            )""",
        f"""CREATE TABLE IF NOT EXISTS {t('encrypted_fields')} (
                subject        {d.text_type} NOT NULL,
                field          {d.text_type} NOT NULL,
                data_class     {d.text_type} NOT NULL,
                version        {d.big_int} NOT NULL,
                key_generation {d.big_int} NOT NULL,
                nonce_hex      {d.text_type} NOT NULL,
                body_hex       {d.text_type} NOT NULL,
                PRIMARY KEY (subject, field)
            )""",
    ]


class SqlCustodyStore:
    """Custody state and encrypted rows in SQLite or PostgreSQL."""

    def __init__(self, database: SqlDatabase) -> None:
        self.database = database
        with database.transaction() as unit:
            for statement in custody_schema(database):
                unit.execute(statement)

    @classmethod
    def open(cls, url: str, schema: str = "fssaira_custody") -> SqlCustodyStore:
        """``sqlite:///path`` or ``postgresql://…``; no application tables are created."""
        if url.startswith("sqlite://"):
            path = url.replace("sqlite:///", "").replace("sqlite://", "") or ":memory:"
            return cls(open_sqlite(path, schema, create_schema=False))
        if url.startswith(("postgres://", "postgresql://")):
            return cls(open_postgres(url, schema, create_schema=False))
        raise ValueError("custody store URL must be sqlite:/// or postgresql://")

    # -- load --------------------------------------------------------------
    def load(self) -> dict:
        t = self.database.table
        with self.database.transaction() as unit:
            generations = {r[0]: int(r[1]) for r in unit.all(
                f"SELECT data_class, generation FROM {t('custody_kek_generations')}")}
            wrapped = {
                (r[0], r[1]): WrappedKey(r[1], int(r[2]), int(r[3]),
                                         bytes.fromhex(r[4]), bytes.fromhex(r[5]))
                for r in unit.all(
                    f"SELECT subject, data_class, kek_generation, key_generation, nonce_hex, "
                    f"body_hex FROM {t('custody_wrapped_keys')}")
            }
            journal = [
                ErasureEntry(int(r[0]), r[1], float(r[2]), r[3], r[4])
                for r in unit.all(
                    f"SELECT seq, subject, erased_at, erased_by, reason "
                    f"FROM {t('custody_erasures')} ORDER BY seq")
            ]
            destroyed = {r[0] for r in unit.all(f"SELECT subject FROM {t('custody_destroyed')}")}
        return {"generations": generations, "wrapped": wrapped, "journal": journal,
                "destroyed": destroyed}

    # -- custody writes ----------------------------------------------------
    def _put_wrapped(self, unit, subject: str, key: WrappedKey) -> None:
        unit.execute(
            f"INSERT INTO {self.database.table('custody_wrapped_keys')} "
            "(subject, data_class, kek_generation, key_generation, nonce_hex, body_hex) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT (subject, data_class) DO UPDATE SET "
            "kek_generation = EXCLUDED.kek_generation, key_generation = EXCLUDED.key_generation, "
            "nonce_hex = EXCLUDED.nonce_hex, body_hex = EXCLUDED.body_hex",
            (subject, key.data_class, key.kek_generation, key.key_generation,
             key.nonce.hex(), key.body.hex()),
        )

    def _put_generation(self, unit, data_class: str, generation: int) -> None:
        unit.execute(
            f"INSERT INTO {self.database.table('custody_kek_generations')} (data_class, generation) "
            "VALUES (?, ?) ON CONFLICT (data_class) DO UPDATE SET generation = EXCLUDED.generation",
            (data_class, generation),
        )

    def save_new_key(self, subject: str, key: WrappedKey) -> None:
        with self.database.transaction() as unit:
            self._put_generation(unit, key.data_class, key.kek_generation)
            self._put_wrapped(unit, subject, key)

    def save_erasure(self, subject: str, entry: ErasureEntry) -> None:
        t = self.database.table
        with self.database.transaction() as unit:
            unit.execute(f"DELETE FROM {t('custody_wrapped_keys')} WHERE subject = ?", (subject,))
            unit.execute(f"INSERT INTO {t('custody_destroyed')} (subject) VALUES (?) "
                         "ON CONFLICT (subject) DO NOTHING", (subject,))
            unit.execute(
                f"INSERT INTO {t('custody_erasures')} (seq, subject, erased_at, erased_by, reason) "
                "VALUES (?, ?, ?, ?, ?)",
                (entry.seq, entry.subject, entry.erased_at, entry.erased_by, entry.reason),
            )

    def save_rotation(self, data_class: str, generation: int,
                      keys: dict[tuple[str, str], WrappedKey]) -> None:
        with self.database.transaction() as unit:
            self._put_generation(unit, data_class, generation)
            for (subject, _cls), key in keys.items():
                self._put_wrapped(unit, subject, key)

    def save_restore(self, wrapped: dict[tuple[str, str], WrappedKey], destroyed: set[str],
                     journal: list[ErasureEntry]) -> None:
        t = self.database.table
        with self.database.transaction() as unit:
            unit.execute(f"DELETE FROM {t('custody_wrapped_keys')}")
            for (subject, _cls), key in wrapped.items():
                self._put_wrapped(unit, subject, key)
            unit.execute(f"DELETE FROM {t('custody_destroyed')}")
            for subject in sorted(destroyed):
                unit.execute(f"INSERT INTO {t('custody_destroyed')} (subject) VALUES (?)",
                             (subject,))
            for entry in journal:
                unit.execute(
                    f"INSERT INTO {t('custody_erasures')} (seq, subject, erased_at, erased_by, "
                    "reason) VALUES (?, ?, ?, ?, ?) ON CONFLICT (seq) DO NOTHING",
                    (entry.seq, entry.subject, entry.erased_at, entry.erased_by, entry.reason),
                )

    # -- encrypted rows ----------------------------------------------------
    def save_rows(self, rows: dict[tuple[str, str], Ciphertext]) -> None:
        with self.database.transaction() as unit:
            for (subject, name), c in rows.items():
                unit.execute(
                    f"INSERT INTO {self.database.table('encrypted_fields')} "
                    "(subject, field, data_class, version, key_generation, nonce_hex, body_hex) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (subject, field) DO UPDATE SET "
                    "data_class = EXCLUDED.data_class, version = EXCLUDED.version, "
                    "key_generation = EXCLUDED.key_generation, nonce_hex = EXCLUDED.nonce_hex, "
                    "body_hex = EXCLUDED.body_hex",
                    (subject, name, c.data_class, c.version, c.key_generation,
                     c.nonce.hex(), c.body.hex()),
                )

    def replace_rows(self, rows: dict[tuple[str, str], Ciphertext]) -> None:
        with self.database.transaction() as unit:
            unit.execute(f"DELETE FROM {self.database.table('encrypted_fields')}")
        self.save_rows(rows)

    def load_rows(self) -> dict[tuple[str, str], Ciphertext]:
        with self.database.transaction() as unit:
            return {
                (r[0], r[1]): Ciphertext(r[0], r[1], r[2], int(r[3]), int(r[4]),
                                         bytes.fromhex(r[5]), bytes.fromhex(r[6]))
                for r in unit.all(
                    f"SELECT subject, field, data_class, version, key_generation, nonce_hex, "
                    f"body_hex FROM {self.database.table('encrypted_fields')}")
            }


def load_master_key(path: str | os.PathLike) -> bytes:
    """Read a 32-byte master key (raw or hex) from a file only its owner can read.

    Generate one with ``python -c "import secrets; print(secrets.token_hex(32))" > key``
    and ``chmod 600 key``. In production, mount it from a secret manager.
    """
    key_path = Path(path)
    mode = key_path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise PermissionError(f"{key_path} is readable by other users; chmod 600 it")
    data = key_path.read_bytes().strip()
    if len(data) == 64:
        with contextlib.suppress(ValueError):
            data = bytes.fromhex(data.decode("ascii"))
    if len(data) != 32:
        raise ValueError(f"{key_path} must hold 32 bytes (or 64 hex characters)")
    return data


def custody_from_env(**options):
    """Build durable custody from the environment, or ``None`` if not configured.

    ``FSSAI_CUSTODY_STORE_URL`` selects the custody database. Key-encryption keys
    come from Vault Transit when ``FSSAI_VAULT_ADDR`` is set (see
    :mod:`fssaira.kms_vault`), otherwise from ``FSSAI_CUSTODY_MASTER_KEY_FILE``.
    Configuring a store with neither is refused: durable ciphertext protected by a
    key that dies with the process would be unreadable after the next restart.
    """
    from .key_custody import KeyCustody
    from .kms_vault import VaultTransitKeyWrapper

    url = os.getenv("FSSAI_CUSTODY_STORE_URL")
    if not url:
        return None
    store = SqlCustodyStore.open(url, os.getenv("FSSAI_CUSTODY_SCHEMA", "fssaira_custody"))
    options.setdefault("erasure_journal", os.getenv("FSSAI_CUSTODY_ERASURE_JOURNAL") or None)
    wrapper = VaultTransitKeyWrapper.from_env()
    if wrapper is not None:
        return KeyCustody(key_wrapper=wrapper, store=store, **options), store
    key_file = os.getenv("FSSAI_CUSTODY_MASTER_KEY_FILE")
    if not key_file:
        raise ValueError("FSSAI_CUSTODY_STORE_URL needs FSSAI_VAULT_ADDR or "
                         "FSSAI_CUSTODY_MASTER_KEY_FILE")
    return KeyCustody(master_seed=load_master_key(key_file), store=store, **options), store


__all__ = ["SqlCustodyStore", "custody_from_env", "custody_schema", "load_master_key"]
