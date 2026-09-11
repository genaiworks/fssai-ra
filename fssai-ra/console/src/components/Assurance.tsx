import { useState } from "react";
import { api } from "../api";
import type { ConformanceReport, VerificationReport } from "../types";
import { Card, Empty, Limit, Notice, Pill, Stat } from "./primitives";

/** Assurance is run on demand against the *configured* backends, not against a
 *  reference build. That is the point: an institution that swaps in its own
 *  database or model can press these buttons and find out whether the control
 *  properties survived the swap. */
export function Assurance() {
  const [verification, setVerification] = useState<VerificationReport | null>(null);
  const [conformance, setConformance] = useState<ConformanceReport | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const runVerification = async () => {
    setBusy("verification"); setError("");
    try { setVerification(await api.verification()); }
    catch (e) { setError(String(e)); }
    finally { setBusy(""); }
  };

  const runConformance = async () => {
    setBusy("conformance"); setError("");
    try { setConformance(await api.conformance()); }
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
        actions={<button className="action" onClick={runVerification} disabled={busy !== ""}>
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
        actions={<button className="action" onClick={runConformance} disabled={busy !== ""}>
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
    </>
  );
}
