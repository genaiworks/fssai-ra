import type { ReactNode } from "react";

export function Card({ title, lede, children, actions }: {
  title?: string; lede?: string; children: ReactNode; actions?: ReactNode;
}) {
  return (
    <section className="card">
      {(title || actions) && (
        <div className="row" style={{ justifyContent: "space-between", alignItems: "flex-start" }}>
          {title && <h2>{title}</h2>}
          {actions}
        </div>
      )}
      {lede && <p className="lede">{lede}</p>}
      {children}
    </section>
  );
}

export function Pill({ tone = "neutral", children }: {
  tone?: "ok" | "warn" | "danger" | "info" | "neutral" | "consequential";
  children: ReactNode;
}) {
  return <span className={`pill ${tone}`}>{children}</span>;
}

export function Stat({ label, value, note, tone }: {
  label: string; value: ReactNode; note?: string;
  tone?: "ok" | "warn" | "danger";
}) {
  const color = tone ? `var(--${tone === "ok" ? "ok" : tone === "warn" ? "warn" : "danger"})` : undefined;
  return (
    <div className="stat">
      <div className="label">{label}</div>
      <div className="value" style={{ color }}>{value}</div>
      {note && <div className="note">{note}</div>}
    </div>
  );
}

export function Notice({ tone = "info", code, children }: {
  tone?: "ok" | "warn" | "danger" | "info"; code?: string; children: ReactNode;
}) {
  return (
    <div className={`notice ${tone}`}>
      {code && <span className="code">{code}</span>}
      <p>{children}</p>
    </div>
  );
}

export function Limit({ children }: { children: ReactNode }) {
  return <p className="limit">{children}</p>;
}

export function Json({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
    </label>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="faint" style={{ padding: "10px 0" }}>{children}</p>;
}
