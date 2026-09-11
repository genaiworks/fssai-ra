import { useEffect, useState } from "react";
import { api } from "../api";
import type { EvidencePage } from "../types";
import { Card, Empty, Limit, Notice, Pill } from "./primitives";

const KINDS = ["", "action_intent", "action_outcome", "policy_decision", "ingest", "quarantine"];

export function Evidence() {
  const [page, setPage] = useState<EvidencePage | null>(null);
  const [kind, setKind] = useState("");
  const [offset, setOffset] = useState(0);
  const [expanded, setExpanded] = useState<number | null>(null);
  const [reconciled, setReconciled] = useState<string>("");

  const load = () => {
    api.evidence(offset, 50, kind || undefined).then(setPage).catch(() => undefined);
  };

  useEffect(load, [offset, kind]);

  return (
    <>
      <Card
        title="Decision record"
        lede="Append-only and hash-chained: each record's hash covers the previous one, so a
              silent edit anywhere in the history stops the chain verifying."
        actions={page && (
          page.chain_valid
            ? <Pill tone="ok">chain verified</Pill>
            : <Pill tone="danger">CHAIN BROKEN</Pill>
        )}
      >
        <div className="row" style={{ marginBottom: 12 }}>
          <select value={kind} onChange={(e) => { setKind(e.target.value); setOffset(0); }}
                  style={{ width: "auto" }}>
            {KINDS.map((k) => <option key={k} value={k}>{k || "all record kinds"}</option>)}
          </select>
          <button className="ghost" onClick={load}>Refresh</button>
          <button className="ghost" onClick={() => api.verifyEvidence().then((r) =>
            setReconciled(r.chain_valid ? "Chain re-verified: intact." : "Chain re-verified: ALTERED."))}>
            Verify chain
          </button>
          <span className="spacer" />
          <button className="ghost" disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - 50))}>Newer</button>
          <button className="ghost" disabled={!page || offset + 50 >= page.total}
                  onClick={() => setOffset(offset + 50)}>Older</button>
        </div>

        {reconciled && <Notice tone={reconciled.includes("ALTERED") ? "danger" : "ok"}>{reconciled}</Notice>}

        {!page || page.records.length === 0 ? (
          <Empty>No records yet. Run an action to produce some.</Empty>
        ) : (
          <div className="chain">
            {page.records.map((record) => (
              <div className="chain-row" key={record.seq}>
                <div className="chain-seq">{record.seq}</div>
                <div className="chain-body">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <span className="chain-kind">{record.kind}</span>
                    <button className="ghost" style={{ padding: "2px 8px", fontSize: 11 }}
                            onClick={() => setExpanded(expanded === record.seq ? null : record.seq)}>
                      {expanded === record.seq ? "hide" : "payload"}
                    </button>
                  </div>
                  <div className="chain-hash">
                    prev {record.prev_hash.slice(0, 16)}… → {record.hash.slice(0, 16)}…
                  </div>
                  {expanded === record.seq && (
                    <pre className="chain-payload">{JSON.stringify(record.payload, null, 2)}</pre>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        <Limit>
          Showing {page?.records.length ?? 0} of {page?.total ?? 0} records. Tamper-evidence
          detects an alteration; it does not prevent one. Pair it with separation of duties and
          an independent monitor that recomputes this chain from a second copy.
        </Limit>
      </Card>

      <Card
        title="Recovery"
        lede="If a mutation completed but its outcome record did not, the executor reports an
              uncertain outcome rather than inviting a blind retry. Reconciliation appends the
              pending record exactly once."
      >
        <button className="ghost" onClick={() => api.reconcile().then((r) =>
          setReconciled(`Reconciled ${r.reconciled} outcome(s); ${r.pending_outcomes} pending; durability ${r.durability}.`),
        ).catch((e) => setReconciled(String(e)))}>
          Reconcile pending outcomes
        </button>
        <Limit>
          On the single-transaction profile this always reports zero, because the pending state
          cannot arise: the mutation and its evidence commit together.
        </Limit>
      </Card>
    </>
  );
}
