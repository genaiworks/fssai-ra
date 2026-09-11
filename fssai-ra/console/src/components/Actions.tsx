import { useEffect, useState } from "react";
import { api } from "../api";
import { ApiError } from "../types";
import type { Approval, ExecutionResult, Profile, Proposal, TransitionRule } from "../types";
import { Card, Field, Json, Limit, Notice } from "./primitives";

/** The three-step protocol, rendered as three steps.
 *
 *  The interesting states here are the failures. When the executor refuses, it
 *  returns a stable code naming the control that refused, and the console shows
 *  that code verbatim: "APPROVAL_PAYLOAD_MISMATCH" tells an operator that the
 *  proposal changed after review, which is a governance fact, not an error. */
export function Actions() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [rule, setRule] = useState<TransitionRule | null>(null);
  const [resourceId, setResourceId] = useState("S-104");
  const [evidenceVersion, setEvidenceVersion] = useState("snapshot-1");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [approval, setApproval] = useState<Approval | null>(null);
  const [result, setResult] = useState<ExecutionResult | null>(null);
  const [denial, setDenial] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [tamper, setTamper] = useState(false);

  useEffect(() => {
    api.profile().then((body) => {
      setProfile(body);
      setRule(body.transitions[0] ?? null);
    }).catch(() => undefined);
  }, []);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    setDenial(null);
    try {
      await fn();
    } catch (error) {
      setDenial(error instanceof ApiError ? error : new ApiError(0, "CLIENT_ERROR", String(error)));
    } finally {
      setBusy(false);
    }
  };

  const reset = () => { setProposal(null); setApproval(null); setResult(null); setDenial(null); };

  const seed = () => run(async () => {
    reset();
    if (!rule) return;
    await api.registerResource(resourceId, rule.from_status, 1);
  });

  const propose = () => run(async () => {
    if (!rule) return;
    setApproval(null); setResult(null);
    setProposal(await api.propose({
      operation: rule.operation,
      resource_id: resourceId,
      // Tampering changes the destination state *after* the reviewer would have
      // seen it, which is the exact scenario the digest binding exists for.
      from_status: rule.from_status,
      to_status: tamper ? "a-state-the-reviewer-never-saw" : rule.to_status,
      evidence_version: evidenceVersion,
    }));
  });

  const approve = () => run(async () => {
    if (!proposal) return;
    setApproval(await api.approve(proposal.request_id));
  });

  const execute = () => run(async () => {
    if (!proposal) return;
    setResult(await api.execute(proposal.request_id));
  });

  return (
    <>
      <Card
        title="Propose → approve → execute"
        lede="The only way to change a governed resource. There is no second path that skips a
              step, which is what makes the evidence record complete rather than well-intentioned."
      >
        <div className="grid two">
          <div>
            <Field label="Resource identifier">
              <input value={resourceId} onChange={(e) => setResourceId(e.target.value)} />
            </Field>
            <Field label="Transition">
              <select
                value={rule ? `${rule.operation}|${rule.from_status}|${rule.to_status}` : ""}
                onChange={(e) => {
                  const [operation, from_status, to_status] = e.target.value.split("|");
                  setRule(profile?.transitions.find(
                    (t) => t.operation === operation && t.from_status === from_status && t.to_status === to_status,
                  ) ?? null);
                  reset();
                }}
              >
                {profile?.transitions.map((t) => (
                  <option key={`${t.operation}|${t.from_status}|${t.to_status}`}
                          value={`${t.operation}|${t.from_status}|${t.to_status}`}>
                    {t.operation}: {t.from_status} → {t.to_status}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Evidence version (the data the reviewer saw)">
              <input value={evidenceVersion} onChange={(e) => setEvidenceVersion(e.target.value)} />
            </Field>
            <label className="row" style={{ gap: 8, marginBottom: 12 }}>
              <input type="checkbox" checked={tamper} onChange={(e) => { setTamper(e.target.checked); reset(); }}
                     style={{ width: "auto" }} />
              <span className="muted">Alter the destination state after review (expect a denial)</span>
            </label>
            <div className="row">
              <button className="ghost" onClick={seed} disabled={busy}>Register resource</button>
              <button className="ghost" onClick={reset} disabled={busy}>Reset</button>
            </div>
          </div>

          <div className="steps">
            <Step index={1} state={proposal ? "done" : "todo"} title="Propose"
                  body={proposal
                    ? `request ${proposal.request_id.slice(0, 8)}… against version ${proposal.expected_version}`
                    : "An agent or a person submits a structured proposal. Nothing has changed yet."}
                  action={<button className="action" onClick={propose} disabled={busy || !rule}>Propose</button>} />
            <Step index={2} state={approval ? "done" : "todo"} title="Approve"
                  body={approval
                    ? `${approval.approver} as ${approval.approver_role}, bound to digest ${approval.proposal_digest.slice(0, 12)}…`
                    : "A named human approves this exact proposal. The role comes from your token, never from the request."}
                  action={<button className="action" onClick={approve} disabled={busy || !proposal}>Approve</button>} />
            <Step index={3} state={result ? "done" : denial ? "blocked" : "todo"} title="Execute"
                  body={result
                    ? `${result.case_id} is now ${result.status} at version ${result.version}${result.replayed ? " (replayed — no second mutation)" : ""}`
                    : "The executor re-checks everything, then mutates once and records the outcome."}
                  action={<button className="action" onClick={execute} disabled={busy || !approval}>Execute</button>} />
          </div>
        </div>

        {denial && (
          <Notice tone={denial.status === 202 ? "warn" : "danger"} code={denial.code}>
            {denial.message}
            {denial.code === "APPROVAL_PAYLOAD_MISMATCH" && (
              <><br />The proposal changed after it was reviewed. A changed proposal requires renewed review — that is the rule working, not a bug.</>
            )}
            {denial.code === "OUTCOME_EVIDENCE_PENDING" && (
              <><br />The mutation completed but its outcome record has not landed. Do not retry. Run reconciliation from the Recovery panel.</>
            )}
          </Notice>
        )}

        {result && (
          <Notice tone="ok" code={result.replayed ? "REPLAYED" : "EXECUTED"}>
            Receipt <span className="mono">{result.receipt_hash.slice(0, 24)}…</span>
            {" "}— press Execute again and the same receipt comes back without a second mutation.
          </Notice>
        )}

        <Limit>
          Synthetic resources and a teaching approval key. The signature here demonstrates
          authenticated fields, not secret management or non-repudiation.
        </Limit>
      </Card>

      {(proposal || approval || result) && (
        <Card title="Request artifacts">
          <Json value={{ proposal, approval, result }} />
        </Card>
      )}
    </>
  );
}

function Step({ index, state, title, body, action }: {
  index: number; state: "todo" | "done" | "blocked";
  title: string; body: string; action: React.ReactNode;
}) {
  return (
    <div className={`step ${state === "done" ? "done" : state === "blocked" ? "blocked" : ""}`}>
      <div className="index">{state === "done" ? "✓" : state === "blocked" ? "!" : index}</div>
      <div className="body">
        <h3>{title}</h3>
        <p>{body}</p>
      </div>
      <div>{action}</div>
    </div>
  );
}
