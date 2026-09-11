import { useEffect, useState } from "react";
import { api } from "../api";
import type { Health, Readiness } from "../types";
import { Card, Json, Limit, Notice, Stat } from "./primitives";

const DURABILITY: Record<string, { tone: "ok" | "warn" | "danger"; text: string }> = {
  "single-transaction": {
    tone: "ok",
    text: "The mutation and its evidence commit together. An interrupted outcome is impossible.",
  },
  "best-effort": {
    tone: "warn",
    text: "State is durable, but the register and the ledger are separate stores. An interrupted outcome is possible and must be reconciled.",
  },
  volatile: {
    tone: "danger",
    text: "State is in memory. Every record is lost on restart. Teaching only.",
  },
};

export function Deployment() {
  const [health, setHealth] = useState<Health | null>(null);
  const [readiness, setReadiness] = useState<Readiness | null>(null);
  const [metrics, setMetrics] = useState("");
  const [error, setError] = useState("");

  const refresh = () => {
    api.health().then(setHealth).catch((e) => setError(String(e)));
    api.readiness().then(setReadiness).catch(() => undefined);
    api.metrics().then(setMetrics).catch(() => undefined);
  };

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 15_000);
    return () => clearInterval(timer);
  }, []);

  if (error) return <Card title="Deployment"><Notice tone="danger">{error}</Notice></Card>;
  if (!health) return <Card title="Deployment"><p className="faint">Contacting the control plane…</p></Card>;

  const durability = DURABILITY[health.durability] ?? DURABILITY.volatile;

  return (
    <>
      <Card
        title="What this deployment actually is"
        lede="A reference architecture that boots happily with public test keys and in-memory
              state is a reference architecture that will be deployed that way. So it reports
              its own shortcomings here, with a severity, rather than in a footnote."
      >
        <div className="grid three">
          <Stat label="Profile" value={health.profile} note={`control plane ${health.version}`} />
          <Stat label="Durability" value={health.durability} tone={durability.tone} note={durability.text} />
          <Stat
            label="Evidence chain"
            value={health.evidence_valid ? "verified" : "BROKEN"}
            tone={health.evidence_valid ? "ok" : "danger"}
            note={`${health.evidence_records} record(s)`}
          />
          <Stat
            label="Model backend"
            value={health.model?.active ?? "none"}
            tone={health.model?.fell_back ? "warn" : "ok"}
            note={health.model?.fell_back ? `fell back from ${health.model.requested}` : "as configured"}
          />
          <Stat label="Authentication" value={health.authentication.mode} />
          <Stat
            label="Pending outcomes"
            value={health.pending_outcomes}
            tone={health.pending_outcomes ? "warn" : "ok"}
            note={health.pending_outcomes ? "a mutation completed without its outcome record" : "none awaiting reconciliation"}
          />
        </div>
        {health.model?.detail && <Notice tone="warn">{health.model.detail}</Notice>}
      </Card>

      {readiness && (
        <Card
          title={`Readiness — ${readiness.blocking.length} blocking finding(s)`}
          lede={readiness.note}
        >
          {readiness.ready_for_pilot && (
            <Notice tone="ok">No known teaching defaults are active in this configuration.</Notice>
          )}
          {[...readiness.blocking, ...readiness.warnings].map((finding) => (
            <Notice
              key={finding.code}
              tone={finding.severity === "blocking" || finding.severity === "high" ? "danger"
                : finding.severity === "medium" ? "warn" : "info"}
              code={`${finding.severity.toUpperCase()} · ${finding.code}`}
            >
              {finding.message}
              {finding.remedy && <><br /><span className="faint">→ {finding.remedy}</span></>}
            </Notice>
          ))}
          <Limit>
            Readiness here means only that no known teaching default is active. It is not an
            assessment of the deployment, the domain profile, or the institution&rsquo;s controls.
          </Limit>
        </Card>
      )}

      <Card title="Metrics" lede="The same counters the paper's result tables are built from.">
        <pre className="json">{metrics || "…"}</pre>
      </Card>

      <Card title="Raw health">
        <Json value={health} />
      </Card>
    </>
  );
}
