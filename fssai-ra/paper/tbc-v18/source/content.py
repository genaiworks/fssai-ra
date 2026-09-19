"""Tables and listings shared by the DOCX and print-HTML builds."""

TABLES = {
 "related": (["Prior work", "Established focus", "What this paper examines"], [
  ["Capabilities and information flow [26–28]", "Access boundaries, attenuation, lineage and independent roles", "Their composition across one agent task and its failure paths"],
  ["Injection defence by design [5,9,13]", "Separating control flow from untrusted data", "Persistent memory, revocation and delivery contracts"],
  ["AI control and monitoring [14–20]", "Safety when the model may be subverting the protocol", "Monitoring that may restrict but never grants authority"],
  ["Agent security evaluation [6,7,22–24]", "Measured security and utility under defined tasks", "Named invariant checks, without a benchmark ranking"],
  ["Confinement [29]", "Information carried by otherwise permitted behaviour", "Encoder-specific release traces and their review cost"]],
  [2.0, 2.3, 2.5]),

 "terms": (["Term", "Meaning", "Enforced at"], [
  ["Workload passport", "The approved ceiling for a whole workload", "Admission"],
  ["Task contract", "Scope and purpose of one execution", "Every mediated request"],
  ["Capability envelope", "Operations currently permitted by the intersected rights", "Authorisation"],
  ["Attenuation", "Delegation of a subset of existing rights, never more", "Agent or service delegation"],
  ["Lineage", "Source restrictions retained through derivation", "Retrieval, memory and release"],
  ["Release escrow", "Approval bound to exact bytes and one recipient", "Disclosure"],
  ["Refusal", "No protected operation when any check fails", "Every protected interface"]],
  [1.5, 3.4, 1.9]),

 "assumptions": (["", "Trusted assumption", "Consequence if it does not hold"], [
  ["A1", "Enforcement code and the control store are integrity-protected", "Every property below it is void"],
  ["A2", "Keys and long-lived credentials stay outside the model process", "Mediation can be bypassed entirely"],
  ["A3", "No undeclared interface reaches protected systems", "Mediation is incomplete, so Property 1 is unproven"],
  ["A4", "Operator actions are authenticated and attributable", "Restoration of authority becomes an escalation path"],
  ["A5", "Adapters preserve identity, version and destination semantics", "A local approval is not the effect that actually occurs"]],
  [0.45, 3.3, 3.05]),

 "traceability": (["Adversary capability", "Bounding mechanism", "Named check that must fail without it"], [
  ["Injected content redirects retrieval", "Context gateway authorises before records reach the model", "cross-subject retrieval refused"],
  ["Contaminated memory persists", "Memory gateway reauthorises every later read", "quarantine survives restart"],
  ["Delegation multiplies rights", "Attenuation with depth, population and shared budget caps", "delegated scope cannot exceed ancestor"],
  ["Forged or stale approval", "Approval binds the exact proposal, version and epoch", "stale approval rejected"],
  ["Revocation during delivery", "Per-chunk recheck with no bulk fallback path", "stream_reauthorizes"],
  ["Evidence writer fails during a stop", "Revocation commits before evidence is attempted", "stop_stays_effective"],
  ["Hostile monitor verdict", "Findings may restrict; only an operator restores", "ai_monitor_can_contract"],
  ["Lost acknowledgement on a remote effect", "Intent ledger, operation-bound key, no blind retry", "uncertain effect blocks dependents"],
  ["Approved bytes carry a covert signal", "Release policy removes destination, timing, size and count choice", "trace-alphabet report"]],
  [2.05, 2.75, 2.0]),

 "evidence": (["Mechanism check", "Recorded behaviour", "What the row is not"], [
  ["Controlled comparison", "0/7, then 2/7, then 7/7 hostile proposals contained", "Arm configurations, not model compliance or field rates"],
  ["Six domain profiles", "180/180 hostile contained; 58/58 benign completed", "Configured profiles, not institutional deployments"],
  ["Control ablation", "Each of eight removals re-enables its harmful action", "Control relevance inside those scenarios only"],
  ["Bounded falsification", "104,997 attempts; no counterexample found", "Nothing outside the declared search space"],
  ["Recorded regression", "1,445 tests passed; 37 capability contracts executed", "Source-bound local evidence, not certification"],
  ["Monitor substitution", "No tested prohibited outcome; hostile-monitor utility zero", "Not an evaluation of detector quality"],
  ["Deployment qualification", "Controlled host and TLS checks recorded", "Not institutional host or network evidence"]],
  [1.5, 2.75, 2.55]),
}

LISTINGS = {
 "contract": [
  "contract_id        transcript.correction.commit",
  "protected_asset    student transcript record, authoritative store",
  "permitted_op       version-bound field correction, one subject, one task",
  "enforcement_point  executor.commit_effect - revalidates lease, resource",
  "                   version, replay state, destination, domain invariants",
  "accountable_owner  registrar (an institutional role, not a service account)",
  "failure_test       tests/test_frontier_controls.py -k stale_approval_rejected",
  "evidence_artifact  audit/architecture/full-tests.xml",
  "failure_response   refuse, record the blocked attempt, require fresh review",
 ],
}
