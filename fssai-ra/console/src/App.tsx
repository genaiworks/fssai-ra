import { useEffect, useState } from "react";
import { getToken, setToken } from "./api";
import { Actions } from "./components/Actions";
import { Assurance } from "./components/Assurance";
import { Deployment } from "./components/Deployment";
import { Evidence } from "./components/Evidence";
import { Governance } from "./components/Governance";
import { Intelligence } from "./components/Intelligence";

const TABS = [
  { id: "deployment", label: "Deployment", element: <Deployment /> },
  { id: "governance", label: "Governance", element: <Governance /> },
  { id: "actions", label: "Actions", element: <Actions /> },
  { id: "intelligence", label: "Intelligence", element: <Intelligence /> },
  { id: "evidence", label: "Evidence", element: <Evidence /> },
  { id: "assurance", label: "Assurance", element: <Assurance /> },
] as const;

const DEV_TOKENS = [
  { token: "dev-operator-token", label: "platform operator" },
  { token: "dev-officer-token", label: "support officer" },
  { token: "dev-agent-token", label: "bounded agent" },
  { token: "dev-auditor-token", label: "auditor" },
];

export function App() {
  const [tab, setTab] = useState<(typeof TABS)[number]["id"]>("deployment");
  const [token, setTokenState] = useState(getToken());

  useEffect(() => {
    if (!token) {
      // The console ships pointed at the published development credentials.
      // That is deliberate for a demonstration and is reported as a blocking
      // finding on the Deployment tab, where an operator cannot miss it.
      setToken(DEV_TOKENS[1].token);
      setTokenState(DEV_TOKENS[1].token);
    }
  }, [token]);

  const changeToken = (value: string) => {
    setToken(value);
    setTokenState(value);
  };

  const active = TABS.find((item) => item.id === tab) ?? TABS[0];

  return (
    <div className="shell">
      <header className="top">
        <div className="brand">
          <strong>FSSAI&#8209;RA</strong>
          <span>fail-secure sovereign AI</span>
        </div>
        <nav className="tabs">
          {TABS.map((item) => (
            <button key={item.id} aria-current={item.id === tab} onClick={() => setTab(item.id)}>
              {item.label}
            </button>
          ))}
        </nav>
        <span className="spacer" />
        <label className="row" style={{ gap: 6 }}>
          <span className="faint" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em" }}>
            acting as
          </span>
          <select value={token} onChange={(e) => changeToken(e.target.value)} style={{ width: "auto" }}>
            {DEV_TOKENS.map((item) => (
              <option key={item.token} value={item.token}>{item.label}</option>
            ))}
            {!DEV_TOKENS.some((item) => item.token === token) && (
              <option value={token}>configured token</option>
            )}
          </select>
        </label>
      </header>

      <main>
        <p className="muted" style={{ marginTop: 0, maxWidth: "72ch" }}>
          A model may propose an action. It cannot manufacture the authority to execute it.
          Everything this console does is also available from the <code>fssaira</code> command
          line and the HTTP API — there is no privileged path.
        </p>
        {active.element}
      </main>

      <footer className="bottom">
        Apache-2.0 · Companion to <em>From Model Literacy to System Literacy: Teaching Trust
        by Construction for Agentic AI</em> · Results shown here are fixture observations in a declared
        environment, not a security certification.
      </footer>
    </div>
  );
}
