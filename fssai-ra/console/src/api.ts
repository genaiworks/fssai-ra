import { ApiError } from "./types";
import type {
  Approval, Capability, ConformanceReport, EvidencePage, ExecutionResult, Health,
  InterfaceInventory, ModelProposal, Profile, Proposal, Readiness, Requirement,
  VerificationReport,
} from "./types";

// Resolved defensively: import.meta.env exists under Vite but not in a plain
// Node runtime, and a console that throws on import cannot be smoke-tested.
const BASE = (import.meta as { env?: ImportMetaEnv }).env?.VITE_API_BASE ?? "/api";
const TOKEN_KEY = "fssaira.token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

export function setToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* private browsing, or no storage: the token simply is not remembered */
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers ?? {}),
    },
  });

  const text = await response.text();
  const body = text ? safeJson(text) : null;

  if (!response.ok) {
    // A 409 carries a stable denial code from the executor. Those codes are the
    // whole point of the interface: they say which control refused, so the
    // console shows them verbatim rather than flattening everything to "error".
    const code = (body?.error as string) ?? String(response.status);
    const detail = (body?.detail as string) ?? response.statusText;
    throw new ApiError(response.status, code, detail);
  }
  // 202 means the mutation happened but its evidence is pending. It is not an
  // error and must never be retried blindly.
  if (response.status === 202 && body?.error) {
    throw new ApiError(202, body.error as string, body.detail as string);
  }
  return body as T;
}

function safeJson(text: string): any {
  try {
    return JSON.parse(text);
  } catch {
    return { detail: text.slice(0, 500) };
  }
}

export const api = {
  health: () => call<Health>("/health"),
  readiness: () => call<Readiness>("/readiness"),
  metrics: async () => {
    const response = await fetch(`${BASE}/metrics`);
    return response.text();
  },
  profile: () => call<Profile>("/v1/profile"),
  contract: () => call<{ requirements: Requirement[]; count: number; domains: string[] }>("/v1/contract"),
  capabilities: () => call<{ capabilities: Capability[] }>("/v1/capabilities"),
  interfaces: () => call<InterfaceInventory>("/v1/interfaces"),

  registerResource: (resource_id: string, status: string, version = 1) =>
    call<{ resource_id: string; status: string; version: number }>("/v1/resources", {
      method: "POST",
      body: JSON.stringify({ resource_id, status, version }),
    }),
  resource: (id: string) => call<{ resource_id: string; status: string; version: number }>(`/v1/resources/${encodeURIComponent(id)}`),

  propose: (body: {
    operation: string; resource_id: string; from_status: string;
    to_status: string; evidence_version: string;
  }) => call<Proposal>("/v1/proposals", { method: "POST", body: JSON.stringify(body) }),
  approve: (requestId: string, ttl_seconds = 300) =>
    call<Approval>(`/v1/proposals/${encodeURIComponent(requestId)}/approval`, {
      method: "POST",
      body: JSON.stringify({ ttl_seconds }),
    }),
  execute: (requestId: string) =>
    call<ExecutionResult>(`/v1/proposals/${encodeURIComponent(requestId)}/execute`, { method: "POST" }),
  proposalEvidence: (requestId: string) =>
    call<{ request_id: string; records: EvidencePage["records"] }>(`/v1/proposals/${encodeURIComponent(requestId)}/evidence`),

  evidence: (offset = 0, limit = 50, kind?: string) =>
    call<EvidencePage>(`/v1/evidence?offset=${offset}&limit=${limit}${kind ? `&kind=${kind}` : ""}`),
  verifyEvidence: () => call<{ chain_valid: boolean; records: number; note: string }>("/v1/evidence/verify"),

  verification: () => call<VerificationReport>("/v1/verification"),
  conformance: () => call<ConformanceReport>("/v1/conformance"),

  proposeTask: (task: string, evidence: string[]) =>
    call<{ model: string; proposals: ModelProposal[]; note: string }>("/v1/propose-task", {
      method: "POST",
      body: JSON.stringify({ task, evidence }),
    }),

  reconcile: () =>
    call<{ reconciled: number; pending_outcomes: number; durability: string }>("/v1/recovery/reconcile", {
      method: "POST",
    }),
};
