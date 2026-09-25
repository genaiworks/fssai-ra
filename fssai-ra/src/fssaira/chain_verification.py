"""Recompute an archived evidence chain from plain rows.

The same checks run in both scale tiers. The Spark job
(``jobs/verify_evidence_chain.py``) reads rows from the Iceberg archive; the
small-data verifier (:mod:`fssaira.small_data`) reads them from a SQLite
archive. Neither trusts the control plane's own report of its chain: the rows
are recomputed here, in a different process, from the archived copy.

Each row needs ``seq``, ``ts``, ``kind``, ``payload_json``, ``prev_hash`` and
``hash``. See :func:`verify_rows` for the verdict.
"""
from __future__ import annotations

import hashlib
import json

GENESIS_HASH = "0" * 64


def recompute(seq: int, ts: float, kind: str, payload_json: str, prev_hash: str) -> str:
    body = json.dumps(
        {"seq": seq, "ts": ts, "kind": kind,
         "payload": json.loads(payload_json), "prev": prev_hash},
        sort_keys=True, default=str,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def verify_rows(rows: list[dict], *, since_seq: int = 0, checkpoint: dict | None = None,
                public_keys: dict[str, str] | None = None,
                anchor_hash: str | None = None) -> dict:
    """Pure verification over archived rows sorted by ``seq``. No Spark needed.

    With ``since_seq`` the first row's predecessor is trusted, unless
    ``anchor_hash`` gives the hash of record ``since_seq - 1`` as already
    verified; then the first row must link to it.
    """
    if checkpoint is not None and since_seq:
        raise ValueError("--checkpoint verifies the whole chain; drop --since-seq")
    if not rows:
        verdict = {"records": 0, "verdict": "EMPTY"}
        if checkpoint is not None:
            verdict["checkpoint"] = {"valid": checkpoint["count"] == 0,
                                     "code": "LEDGER_TRUNCATED" if checkpoint["count"] else "EMPTY"}
            verdict["verdict"] = "EMPTY" if checkpoint["count"] == 0 else "COMPROMISED"
        return verdict

    seen: dict[int, int] = {}
    for row in rows:
        seen[row["seq"]] = seen.get(row["seq"], 0) + 1
    duplicates = sorted(seq for seq, count in seen.items() if count > 1)
    # Check the chain over one copy of each record; duplicates are reported separately.
    unique, taken = [], set()
    for row in rows:
        if row["seq"] not in taken:
            taken.add(row["seq"])
            unique.append(row)

    if since_seq == 0:
        previous = GENESIS_HASH
    else:
        previous = anchor_hash if anchor_hash is not None else unique[0]["prev_hash"]
    expected_seq = since_seq
    hash_failures, link_failures, gaps = [], [], []
    for row in unique:
        if row["seq"] != expected_seq:
            gaps.append({"expected": expected_seq, "found": row["seq"]})
            expected_seq = row["seq"]
        if row["prev_hash"] != previous:
            link_failures.append(row["seq"])
        if recompute(row["seq"], row["ts"], row["kind"], row["payload_json"],
                     row["prev_hash"]) != row["hash"]:
            hash_failures.append(row["seq"])
        previous = row["hash"]
        expected_seq += 1

    verdict = {
        "records": len(rows),
        "first_seq": unique[0]["seq"],
        "last_seq": unique[-1]["seq"],
        "scope": ("internal consistency plus signed checkpoint" if checkpoint is not None
                  else "internal consistency only; no independent checkpoint"),
        "tail_truncation_checked": checkpoint is not None,
        "chain_valid": not hash_failures,
        "links_intact": not link_failures,
        "sequence_complete": not gaps,
        "no_duplicates": not duplicates,
        "altered_records": hash_failures[:50],
        "broken_links": link_failures[:50],
        "sequence_gaps": gaps[:50],
        "duplicate_seqs": duplicates[:50],
    }
    failed = bool(hash_failures or link_failures or gaps or duplicates)
    if checkpoint is not None:
        from fssaira.evidence import EvidenceRecord
        from fssaira.evidence_notary import Checkpoint, verify_against_checkpoint

        records = [
            EvidenceRecord(row["seq"], row["ts"], row["kind"], json.loads(row["payload_json"]),
                           row["prev_hash"], row["hash"])
            for row in unique
        ]
        keys = {key_id: bytes.fromhex(value) for key_id, value in (public_keys or {}).items()}
        result = verify_against_checkpoint(records, Checkpoint(**checkpoint), keys)
        verdict["checkpoint"] = {"valid": result.valid, "code": result.code,
                                 "detail": result.detail}
        failed = failed or not result.valid
    verdict["verdict"] = "COMPROMISED" if failed else "INTACT"
    return verdict


__all__ = ["GENESIS_HASH", "recompute", "verify_rows"]
