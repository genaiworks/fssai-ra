"""Tables and listings shared by the DOCX and print-HTML builds (V19)."""

TABLES = {
 "patterns": (["Pattern", "The implicit authority it removes", "Refusal that proves it"], [
  ["P1 Declared ceiling", "A workload whose reachable data, tools, zones and effects were never written down", "An undeclared interface is refused at the boundary"],
  ["P2 Task contract", "A session that keeps yesterday's scope for today's purpose", "A request outside purpose, subject, destination or expiry is refused"],
  ["P3 Credentialless runtime", "A model process holding a database, cloud or signing credential", "A call without a live scoped lease is refused"],
  ["P4 Attenuated delegation", "A spawned agent that starts with fresh authority and a fresh budget", "A child scope wider than its ancestor is refused"],
  ["P5 Mediated context", "Retrieval that authorises after the record has reached the model", "A read outside subject or cumulative scope is refused"],
  ["P6 Reauthorised memory", "Stored context that is trusted because it was once authorised", "A read of quarantined or unauthorised memory is refused"],
  ["P7 Typed effect", "Natural language that reaches a system as a command", "A proposal with a stale version, replay or unknown destination is refused"],
  ["P8 Sealed release", "Approval of a summary while different bytes leave the building", "A changed artifact, recipient or epoch refuses the next chunk and the bulk path"],
  ["P9 Restricting monitor", "An assurance component that can hand back a privilege", "An automated restoration of authority is refused"],
  ["P10 Declared graph", "Agents that are each in policy and jointly out of it", "A protected-source-to-public-sink path is refused before the terminal agent acts"]],
  [1.55, 2.75, 2.5]),

 "obligations": (["", "What the deployment must build", "What the reference supplies for it"], [
  ["B1", "Enforcement code and the control store the model cannot write", "Isolation probes that record satisfied, violated or not measured"],
  ["B2", "Key and credential custody outside the model process", "A credentialless runtime and lease broker to build against"],
  ["B3", "One declared path to every protected system", "The effect and disclosure inventory that makes the set enumerable"],
  ["B4", "Authenticated, attributable operator action", "Operator interfaces separate from agent interfaces, bounded by the ceiling"],
  ["B5", "Adapters that preserve identity, version and destination", "A conformance suite and settlement contract each adapter must pass"]],
  [0.4, 3.1, 3.3]),

 "evidence": (["Mechanism check", "Recorded behaviour", "Reading"], [
  ["Controlled comparison", "0/7, then 2/7, then 7/7 hostile proposals contained", "The patterns, not the prompt, produce containment"],
  ["Six domain profiles", "180/180 hostile contained; 58/58 benign completed", "The catalogue rebinds without core changes"],
  ["Pattern ablation", "Each of eight removals re-enables its harmful action", "No pattern in the set is decorative"],
  ["Bounded falsification", "104,997 attempts; no counterexample in the declared space", "The design rule survives its own search"],
  ["Recorded regression", "1,445 tests passed; 37 capability contracts executed", "Every guarantee names a test that fails without it"]],
  [1.5, 2.85, 2.45]),
}

LISTINGS = {
 "contract": [
  "contract_id        transcript.correction.commit",
  "pattern            P7 typed effect  +  P2 task contract",
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
