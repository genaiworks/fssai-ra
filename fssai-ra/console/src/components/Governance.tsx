import { useEffect, useState } from "react";
import { api } from "../api";
import type { Capability, InterfaceInventory, Profile, Requirement } from "../types";
import { Card, Empty, Limit, Pill } from "./primitives";

export function Governance() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [requirements, setRequirements] = useState<Requirement[]>([]);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [interfaces, setInterfaces] = useState<InterfaceInventory | null>(null);

  useEffect(() => {
    api.profile().then(setProfile).catch(() => undefined);
    api.contract().then((body) => setRequirements(body.requirements)).catch(() => undefined);
    api.capabilities().then((body) => setCapabilities(body.capabilities)).catch(() => undefined);
    api.interfaces().then(setInterfaces).catch(() => undefined);
  }, []);

  return (
    <>
      <Card
        title="Application profile"
        lede="Every transition below is enforced by the executor. A transition that is not
              declared here cannot be approved, however legitimate it looks."
      >
        {profile ? (
          <>
            <div className="row" style={{ marginBottom: 12 }}>
              <Pill tone="info">{profile.profile_id} v{profile.version}</Pill>
              <span className="muted">{profile.title}</span>
              <span className="faint">owner: {profile.owner}</span>
            </div>
            <div className="scroll-x">
              <table>
                <thead>
                  <tr><th>Operation</th><th>From</th><th>To</th><th>Review</th><th>Approval role</th></tr>
                </thead>
                <tbody>
                  {profile.transitions.map((rule) => (
                    <tr key={`${rule.operation}:${rule.from_status}:${rule.to_status}`}>
                      <td className="mono">{rule.operation}</td>
                      <td className="mono">{rule.from_status}</td>
                      <td className="mono">{rule.to_status}</td>
                      <td>
                        {rule.consequential
                          ? <Pill tone="consequential">needs a named human</Pill>
                          : <Pill tone="neutral">reversible</Pill>}
                      </td>
                      <td className="mono">{rule.approval_role}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Limit><strong>Manual fallback.</strong> {profile.manual_fallback}</Limit>
          </>
        ) : <Empty>No profile loaded.</Empty>}
      </Card>

      <Card
        title="Capability catalogue"
        lede="What a model is permitted to propose, and the review level each proposal carries.
              The class is read from here, never from the model's own output — a model that
              labels an award approval 'reversible' changes nothing."
      >
        <div className="scroll-x">
          <table>
            <thead>
              <tr><th>Tool</th><th>Authoritative class</th><th>Egress</th><th>Description</th></tr>
            </thead>
            <tbody>
              {capabilities.map((capability) => (
                <tr key={capability.tool}>
                  <td className="mono">{capability.tool}</td>
                  <td>
                    {capability.action_class === "high_impact"
                      ? <Pill tone="consequential">high impact</Pill>
                      : <Pill tone="neutral">reversible</Pill>}
                  </td>
                  <td>{capability.egress ? <Pill tone="danger">egress</Pill> : <span className="faint">—</span>}</td>
                  <td className="muted">{capability.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <Card
        title={`Control contract — ${requirements.length} requirement(s)`}
        lede="Seven fields per requirement. If a capability cannot fill all seven, it is not
              ready to be automated; that is the diagnostic, not an inconvenience."
      >
        {requirements.length === 0 && <Empty>The control plane could not read the contract directory.</Empty>}
        {requirements.map((requirement) => (
          <details key={requirement.id} style={{ borderBottom: "1px solid var(--line)", padding: "10px 0" }}>
            <summary style={{ cursor: "pointer" }}>
              <span className="mono" style={{ color: "var(--accent)" }}>{requirement.id}</span>{" "}
              <span className="muted">{requirement.protected_asset}</span>
            </summary>
            <div className="scroll-x" style={{ marginTop: 10 }}>
              <table>
                <tbody>
                  {([
                    ["Protected asset", requirement.protected_asset],
                    ["Permitted operation", requirement.permitted_operation],
                    ["Enforcement point", requirement.enforcement_point],
                    ["Owner", requirement.owner],
                    ["Failure test", requirement.test],
                    ["Evidence artifact", requirement.evidence_artifact],
                    ["Failure response", requirement.failure_response],
                  ] as const).map(([label, value]) => (
                    <tr key={label}>
                      <td className="faint nowrap" style={{ width: 180 }}>{label}</td>
                      <td>{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        ))}
      </Card>

      {interfaces && (
        <Card
          title="Interface inventory"
          lede="A hardware diode governs exactly one link. Every other path needs its own named
                control and owner, or the directional claim is about a link nobody attacks."
        >
          <div className="scroll-x">
            <table>
              <thead><tr><th>Interface</th><th>Direction</th><th>Control</th><th>Owner</th></tr></thead>
              <tbody>
                {interfaces.interfaces.map((item) => (
                  <tr key={item.name}>
                    <td>{item.name}{item.note && <div className="faint">{item.note}</div>}</td>
                    <td>
                      <Pill tone={item.direction === "inward" ? "ok" : item.direction === "outward" ? "warn" : "danger"}>
                        {item.direction}
                      </Pill>
                    </td>
                    <td className="muted">{item.control}</td>
                    <td className="mono">{item.owner}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Limit>
            {interfaces.outward_capable} of {interfaces.count} declared interfaces can carry data
            outward. {interfaces.complete
              ? "Every one has a named control and owner."
              : `Uncontrolled: ${interfaces.uncontrolled.join(", ")}.`}
          </Limit>
        </Card>
      )}
    </>
  );
}
