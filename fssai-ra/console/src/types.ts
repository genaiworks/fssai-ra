/** Shapes returned by the control plane. Kept narrow on purpose: the console
 *  renders what the API says and never re-derives a governance decision. */

export interface TransitionRule {
  operation: string;
  from_status: string;
  to_status: string;
  consequential: boolean;
  approval_role: string;
}

export interface Profile {
  profile_id: string;
  version: string;
  title: string;
  resource_name: string;
  owner: string;
  manual_fallback: string;
  transitions: TransitionRule[];
}

export interface Health {
  status: string;
  version: string;
  profile: string;
  durability: "volatile" | "best-effort" | "single-transaction";
  evidence_valid: boolean;
  evidence_records: number;
  pending_outcomes: number;
  model: { requested: string; active: string; fell_back: boolean; detail: string } | null;
  authentication: { mode: string; warnings: string[] };
  configuration_warnings: string[];
}

export interface Finding {
  severity: "blocking" | "high" | "medium" | "info";
  code: string;
  message: string;
  remedy: string;
}

export interface Readiness {
  ready_for_pilot: boolean;
  blocking: Finding[];
  warnings: Finding[];
  note: string;
}

export interface Requirement {
  id: string;
  domain: string;
  protected_asset: string;
  permitted_operation: string;
  enforcement_point: string;
  owner: string;
  test: string;
  evidence_artifact: string;
  failure_response: string;
}

export interface Capability {
  tool: string;
  operation: string;
  action_class: "reversible" | "high_impact";
  egress: boolean;
  description: string;
  argument_names: string[];
}

export interface EvidenceRecord {
  seq: number;
  ts: number;
  kind: string;
  payload: Record<string, unknown>;
  prev_hash: string;
  hash: string;
}

export interface EvidencePage {
  total: number;
  offset: number;
  limit: number;
  chain_valid: boolean;
  records: EvidenceRecord[];
}

export interface Proposal {
  request_id: string;
  requester: string;
  operation: string;
  case_id: string;
  expected_version: number;
  from_status: string;
  to_status: string;
  evidence_version: string;
}

export interface Approval {
  approval_id: string;
  proposal_digest: string;
  approver: string;
  approver_role: string;
  audience: string;
  expires_at: number;
  key_id: string;
  signature: string;
}

export interface ExecutionResult {
  request_id: string;
  case_id: string;
  version: number;
  status: string;
  receipt_hash: string;
  replayed: boolean;
}

export interface VerificationReport {
  summary: {
    states_explored: number;
    mutations_observed: number;
    invariants_checked: number;
    violations: number;
    holds: boolean;
  };
  invariants: string[];
  bounds: Record<string, unknown>;
  outcome_histogram: Record<string, number>;
  violations: { invariant: string; configuration: string; detail: string }[];
}

export interface ConformanceReport {
  backends: Record<string, string>;
  summary: {
    checks_total: number;
    checks_executed: number;
    checks_skipped: number;
    checks_passed: number;
    checks_failed: number;
    conformant: boolean;
  };
  checks: {
    id: string;
    domain: string;
    requirement: string;
    title: string;
    passed: boolean;
    detail: string;
    skipped: boolean;
  }[];
}

export interface ModelProposal {
  tool: string;
  operation: string;
  target: string;
  args: Record<string, unknown>;
  rationale: string;
  declared_class: string;
  authoritative_class: string;
  egress: boolean;
  requires_named_human: boolean;
}

export interface InterfaceInventory {
  interfaces: { name: string; direction: string; control: string; owner: string; note: string }[];
  count: number;
  outward_capable: number;
  uncontrolled: string[];
  complete: boolean;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message);
  }
}
