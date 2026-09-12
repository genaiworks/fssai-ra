import { useState } from "react";
import { api } from "../api";
import type {
  AssistedReviewReport, ConformanceReport, CoverageReport, DelegationReport, VerificationReport,
} from "../types";
import { Card, Empty, Limit, Notice, Pill, Stat } from "./primitives";

/** Assurance is run on demand against the *configured* backends, not against a
 *  reference build. That is the point: an institution that swaps in its own
 *  database or model can press these buttons and find out whether the control
 *  properties survived the swap. */
export function Assurance() {
  const [verification, setVerification] = useState<VerificationReport | null>(null);
  const [conformance, setConformance] = useState<ConformanceReport | null>(null);
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
  const [delegation, setDelegation] = useState<DelegationReport | null>(null);
  const [assisted, setAssisted] = useState<AssistedReviewReport | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  /** Every card runs a real check against this deployment and can fail. One
   *  wrapper so a failure surfaces as a notice rather than an unhandled
   *  rejection in a governance console. */
  const run = async <T,>(name: string, call: () => Promise<T>, set: (value: T) => void) => {
    setBusy(name); setError("");
    try { set(await call()); }
    catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  };

  return (
    <>
      {error && <Notice tone="danger">{error}</Notice>}

      <Card
        title="Bounded model check"
        lede="A hand-written attack suite proves the attacks someone imagined are contained. This
              enumerates the profile's whole declared authority space and runs the real executor
              against every combination, then checks five invariants over the results."
        actions={<button className="action" onClick={() => run("verification", api.verification, setVerification)} disabled={busy !== ""}>
          {busy === "verification" ? "Exploring…" : "Run check"}
        </button>}
      >
        {!verification ? <Empty>Not yet run.</Empty> : (
          <>
            <div className="grid three">
              <Stat label="States explored" value={verification.summary.states_explored} />
              <Stat label="Mutations observed" value={verification.summary.mutations_observed}
                    note="only fully authorized configurations" />
              <Stat label="Violations" value={verification.summary.violations}
                    tone={verification.summary.holds ? "ok" : "danger"} />
            </div>

            <h3 style={{ fontSize: 13, marginTop: 18, marginBottom: 6 }}>Invariants checked</h3>
            <ul className="muted" style={{ paddingLeft: 18, margin: 0 }}>
              {verification.invariants.map((invariant) => <li key={invariant}>{invariant}</li>)}
            </ul>

            <h3 style={{ fontSize: 13, marginTop: 18, marginBottom: 6 }}>Denial outcomes observed</h3>
            <div className="scroll-x">
              <table>
                <thead><tr><th>Outcome</th><th className="right">Configurations</th></tr></thead>
                <tbody>
                  {Object.entries(verification.outcome_histogram)
                    .sort((a, b) => b[1] - a[1])
                    .map(([code, count]) => (
                      <tr key={code}>
                        <td className="mono">
                          {code === "EXECUTED" ? <Pill tone="ok">{code}</Pill> : code}
                        </td>
                        <td className="right mono">{count}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            {verification.violations.map((violation, index) => (
              <Notice key={index} tone="danger" code="VIOLATION">
                <span className="mono">{violation.configuration}</span> — {violation.detail}
              </Notice>
            ))}

            <Limit>{String(verification.bounds.note)}</Limit>
          </>
        )}
      </Card>

      <Card
        title="Conformance"
        lede="The same properties, run against whatever backends this deployment has actually
              configured. Replacing a component is only safe if the suite still passes."
        actions={<button className="action" onClick={() => run("conformance", api.conformance, setConformance)} disabled={busy !== ""}>
          {busy === "conformance" ? "Checking…" : "Run suite"}
        </button>}
      >
        {!conformance ? <Empty>Not yet run.</Empty> : (
          <>
            <div className="row" style={{ marginBottom: 14 }}>
              {conformance.summary.conformant
                ? <Pill tone="ok">conformant</Pill>
                : <Pill tone="danger">NOT CONFORMANT</Pill>}
              <span className="muted">
                {conformance.summary.checks_passed}/{conformance.summary.checks_executed} checks passed
                {conformance.summary.checks_skipped > 0 && `, ${conformance.summary.checks_skipped} skipped`}
              </span>
            </div>

            <div className="row" style={{ marginBottom: 14 }}>
              {Object.entries(conformance.backends).map(([port, name]) => (
                <Pill key={port} tone={name === "not supplied" ? "neutral" : "info"}>{port}: {name}</Pill>
              ))}
            </div>

            <div className="scroll-x">
              <table>
                <thead><tr><th>Check</th><th>Requirement</th><th>Property</th><th>Result</th></tr></thead>
                <tbody>
                  {conformance.checks.map((check) => (
                    <tr key={check.id}>
                      <td className="mono">{check.id}</td>
                      <td className="mono faint">{check.requirement}</td>
                      <td>{check.title}
                        {check.detail && !check.passed && <div className="faint">{check.detail}</div>}
                      </td>
                      <td>
                        {check.skipped ? <Pill tone="neutral">skipped</Pill>
                          : check.passed ? <Pill tone="ok">pass</Pill>
                          : <Pill tone="danger">FAIL</Pill>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Limit>
              Behavioural conformance for these fixtures in this environment. Not a penetration
              test, an audit, or a certification.
            </Limit>
          </>
        )}
      </Card>

      <Card
        title="Control-contract coverage"
        lede="Every requirement states a failure test. This asks the harder question: does that
              test exist? A control described in a document and bound to nothing that runs
              disappears the first time someone refactors, and nothing goes red."
        actions={<button className="action" onClick={() => run("coverage", api.coverage, setCoverage)} disabled={busy !== ""}>
          {busy === "coverage" ? "Measuring…" : "Measure coverage"}
        </button>}
      >
        {!coverage ? <Empty>Not yet run.</Empty> : (
          <>
            <div className="grid three">
              <Stat label="Machine-verified" value={coverage.totals.machine_verified}
                    note="an executable check is bound to it" />
              <Stat label="Attested" value={coverage.totals.organizationally_attested}
                    note="a named role, on a declared cadence" />
              <Stat label="Unverified" value={coverage.totals.unverified}
                    tone={coverage.totals.unverified === 0 ? "ok" : "danger"}
                    note="a test in prose, bound to nothing" />
            </div>

            {coverage.totals.unverified > 0 && (
              <Notice tone="danger" code="UNVERIFIED">
                {coverage.unverified_requirements.join(", ")} describe a failure test and bind it
                to nothing. A control that exists in review and not at runtime is the failure
                this contract exists to eliminate.
              </Notice>
            )}
            {coverage.bindings_naming_unknown_requirements.length > 0 && (
              <Notice tone="danger" code="STALE BINDING">
                {coverage.bindings_naming_unknown_requirements.join(", ")} — a binding points at a
                requirement that no longer exists.
              </Notice>
            )}

            <div className="scroll-x">
              <table>
                <thead><tr><th>Requirement</th><th>Domain</th><th>Status</th><th>Backed by</th></tr></thead>
                <tbody>
                  {coverage.requirements.map((row) => (
                    <tr key={row.requirement_id}>
                      <td className="mono">{row.requirement_id}</td>
                      <td className="faint">{row.domain}</td>
                      <td>
                        {row.status === "machine_verified" ? <Pill tone="ok">machine-verified</Pill>
                          : row.status === "organizationally_attested" ? <Pill tone="info">attested</Pill>
                          : <Pill tone="danger">UNVERIFIED</Pill>}
                      </td>
                      <td className="faint">
                        {row.status === "organizationally_attested"
                          ? `${row.attested_by} · ${row.attestation_cadence}`
                          : [...new Set(row.bindings.map((b) => b.mechanism))].join(", ") || "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <Limit>{coverage.limits[0]}</Limit>
          </>
        )}
      </Card>

      <Card
        title="Delegated authority"
        lede="Authority travels once an orchestrator spawns sub-agents. These are the same ten
              chains put to three architectures. The middle column is the finding: validating each
              hop against its immediate delegator is a real control, and it is not the same thing
              as verifying the chain."
        actions={<button className="action" onClick={() => run("delegation", api.delegation, setDelegation)} disabled={busy !== ""}>
          {busy === "delegation" ? "Verifying…" : "Run chains"}
        </button>}
      >
        {!delegation ? <Empty>Not yet run.</Empty> : (
          <>
            <div className="grid three">
              {["unguarded", "caller_checked", "this_architecture"].map((arm) => (
                <Stat key={arm}
                      label={arm === "caller_checked" ? "Per-hop check" : arm === "this_architecture" ? "Verify the chain" : "Unguarded"}
                      value={`${delegation.arms[arm]?.contained ?? 0}/${delegation.hostile_chains}`}
                      tone={arm === "this_architecture" ? "ok" : undefined}
                      note={delegation.arms[arm]?.benign_chain_completed ? "benign chain completes" : "benign chain REFUSED"} />
              ))}
            </div>

            <h3 style={{ fontSize: 13, marginTop: 18, marginBottom: 6 }}>Is each invariant load-bearing?</h3>
            <div className="scroll-x">
              <table>
                <thead><tr><th>Invariant</th><th>With</th><th>Without</th><th>Result</th></tr></thead>
                <tbody>
                  {delegation.ablations.map((row) => (
                    <tr key={row.control}>
                      <td>{row.control}</td>
                      <td className="mono faint">{row.with_control}</td>
                      <td className="mono faint">{row.without_control}</td>
                      <td>{row.load_bearing
                        ? <Pill tone="ok">load-bearing</Pill>
                        : <Pill tone="neutral">did not bind</Pill>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="row" style={{ marginTop: 14 }}>
              <Pill tone={delegation.verification.holds ? "ok" : "danger"}>
                {delegation.verification.states_explored} chain shapes, {delegation.verification.violations.length} violations
              </Pill>
            </div>

            <Limit>{delegation.limits[0]}</Limit>
          </>
        )}
      </Card>

      <Card
        title="Assisted review"
        lede="Oversight capacity assumes an unaided reader. Once a model helps the reviewer decide,
              the deliberation floor must fall — and whether that is safe depends on whether the
              assistant is independent of the model writing the proposals."
        actions={<button className="action" onClick={() => run("assisted", api.assistedReview, setAssisted)} disabled={busy !== ""}>
          {busy === "assisted" ? "Running…" : "Run trial"}
        </button>}
      >
        {!assisted ? <Empty>Not yet run.</Empty> : (
          <>
            <div className="grid three">
              <Stat label="Merit failures — unaided" value={assisted.summary.merit_failures_unaided}
                    tone="ok" note={`${assisted.summary.benign_completed_unaided} benign completed`} />
              <Stat label="— dependent assistant" value={assisted.summary.merit_failures_assisted_dependent}
                    tone="danger" note="same model, same evidence packet" />
              <Stat label="— independent assistant" value={assisted.summary.merit_failures_assisted_independent}
                    note={`${assisted.summary.benign_completed_assisted_independent} benign completed`} />
            </div>

            {assisted.summary.every_mechanism_passed_in_the_harmful_arm && (
              <Notice tone="warn" code="NO RUNTIME SIGNAL">
                In the harmful arm the evidence chain is intact, the reviewer is inside quota,
                every approval clears the configured floor, and no oversight refusal fires. There
                is nothing here to alert on — which is why the control is a configuration gate.
              </Notice>
            )}
            {assisted.summary.configuration_gate_refused_the_harmful_arm && (
              <Notice tone="ok" code="GATE BINDS">
                A deployment declaring a dependent assistant and a lowered deliberation floor does
                not start.
              </Notice>
            )}
            {assisted.summary.independence_bounds_harm_without_removing_it && (
              <Notice tone="info" code="CEILING MOVED">
                The independent arm does not reach zero. Assistance multiplies a reviewer's
                effective attention; it does not make attention unbounded. This deployment has a
                larger ceiling to compute, not permission to stop computing one.
              </Notice>
            )}

            <Limit>{assisted.limits[0]}</Limit>
          </>
        )}
      </Card>
    </>
  );
}
