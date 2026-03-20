/**
 * Seabay TypeScript Client
 *
 * Lightweight wrapper around Seabay API.
 */

import type {
  Agent,
  BidirectionalRelationship,
  Circle,
  Intent,
  Introduction,
  Match,
  PaginatedList,
  RegisterResult,
  Relationship,
  SSEvent,
  Task,
} from "./types";

const DEFAULT_BASE_URL = "https://seabay.ai/v1";

export class SeabayClient {
  private baseUrl: string;
  private apiKey: string;

  constructor(apiKey: string, baseUrl: string = DEFAULT_BASE_URL) {
    this.apiKey = apiKey;
    this.baseUrl = baseUrl.replace(/\/+$/, "");
  }

  private async request<T>(method: string, path: string, body?: unknown, params?: Record<string, string>): Promise<T> {
    const url = new URL(`${this.baseUrl}${path}`);
    if (params) {
      Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    }

    const resp = await fetch(url.toString(), {
      method,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });

    if (!resp.ok) {
      const error = await resp.json().catch(() => ({ error: { code: "unknown", message: resp.statusText } }));
      throw new Error(`Seabay API Error: ${error.error?.code} — ${error.error?.message}`);
    }

    return resp.json() as Promise<T>;
  }

  // ── Agent ──

  static async register(slug: string, displayName: string, agentType = "personal", baseUrl = DEFAULT_BASE_URL): Promise<RegisterResult> {
    const resp = await fetch(`${baseUrl}/agents/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug, display_name: displayName, agent_type: agentType }),
    });
    if (!resp.ok) throw new Error("Registration failed");
    return resp.json() as Promise<RegisterResult>;
  }

  getAgent(agentId: string): Promise<Agent> {
    return this.request("GET", `/agents/${agentId}`);
  }

  updateAgent(agentId: string, data: Partial<Agent>): Promise<Agent> {
    return this.request("PATCH", `/agents/${agentId}`, data);
  }

  searchAgents(params: Record<string, string>): Promise<PaginatedList<Agent>> {
    return this.request("GET", "/agents/search", undefined, params);
  }

  // ── Relationships ──

  importRelationship(toAgentId: string, originType = "imported_contact"): Promise<Relationship> {
    return this.request("POST", "/relationships/import", { to_agent_id: toAgentId, origin_type: originType });
  }

  claimRelationship(claimValue: string, claimType = "handle"): Promise<Relationship> {
    return this.request("POST", "/relationships/claim", { claim_value: claimValue, claim_type: claimType });
  }

  listRelationships(params?: Record<string, string>): Promise<PaginatedList<Relationship>> {
    return this.request("GET", "/relationships/my", undefined, params);
  }

  getRelationship(agentId: string): Promise<BidirectionalRelationship> {
    return this.request("GET", `/relationships/${agentId}`);
  }

  blockAgent(agentId: string, block = true): Promise<{ agent_id: string; is_blocked: boolean }> {
    return this.request("POST", `/relationships/${agentId}/block`, { block });
  }

  starAgent(agentId: string, starred = true): Promise<{ agent_id: string; starred: boolean }> {
    return this.request("PUT", `/relationships/${agentId}/star`, { starred });
  }

  // ── Introductions ──

  introduce(targetAId: string, targetBId: string, reason: string): Promise<Introduction> {
    return this.request("POST", "/relationships/introduce", { target_a_id: targetAId, target_b_id: targetBId, reason });
  }

  acceptIntroduction(introductionId: string): Promise<{ id: string; status: string }> {
    return this.request("POST", `/relationships/introduce/${introductionId}/accept`);
  }

  declineIntroduction(introductionId: string): Promise<{ id: string; status: string }> {
    return this.request("POST", `/relationships/introduce/${introductionId}/decline`);
  }

  // ── Circles ──

  createCircle(name: string, options?: Partial<Circle>): Promise<Circle> {
    return this.request("POST", "/circles", { name, ...options });
  }

  getCircle(circleId: string): Promise<Circle> {
    return this.request("GET", `/circles/${circleId}`);
  }

  updateCircle(circleId: string, data: Partial<Circle>): Promise<Circle> {
    return this.request("PATCH", `/circles/${circleId}`, data);
  }

  joinCircle(circleId: string, inviteToken?: string): Promise<{ status: string }> {
    return this.request("POST", `/circles/${circleId}/join`, { invite_token: inviteToken });
  }

  submitJoinRequest(circleId: string, message = ""): Promise<{ id: string; status: string }> {
    return this.request("POST", `/circles/${circleId}/join-requests`, { message });
  }

  listJoinRequests(circleId: string): Promise<{ data: Array<{ id: string; agent_id: string; message: string; status: string }> }> {
    return this.request("GET", `/circles/${circleId}/join-requests`);
  }

  approveJoinRequest(circleId: string, requestId: string): Promise<{ id: string; status: string }> {
    return this.request("POST", `/circles/${circleId}/join-requests/${requestId}/approve`);
  }

  rejectJoinRequest(circleId: string, requestId: string): Promise<{ id: string; status: string }> {
    return this.request("POST", `/circles/${circleId}/join-requests/${requestId}/reject`);
  }

  listCircleMembers(circleId: string): Promise<{ data: Array<{ agent_id: string; display_name: string; role: string }> }> {
    return this.request("GET", `/circles/${circleId}/members`);
  }

  // ── Intents ──

  createIntent(category: string, description: string, options?: Partial<Intent>): Promise<Intent> {
    return this.request("POST", "/intents", { category, description, ...options });
  }

  getIntent(intentId: string): Promise<Intent> {
    return this.request("GET", `/intents/${intentId}`);
  }

  getMatches(intentId: string): Promise<{ data: Match[]; total: number }> {
    return this.request("GET", `/intents/${intentId}/matches`);
  }

  selectMatch(intentId: string, agentId: string, options?: { description?: string; payload_ref?: string }): Promise<{ task_id: string; risk_level: string; status: string }> {
    return this.request("POST", `/intents/${intentId}/select`, { agent_id: agentId, ...options });
  }

  cancelIntent(intentId: string): Promise<Intent> {
    return this.request("POST", `/intents/${intentId}/cancel`);
  }

  // ── Tasks ──

  createTask(toAgentId: string, taskType: string, description: string, options?: Partial<Task>): Promise<Task> {
    return this.request("POST", "/tasks", { to_agent_id: toAgentId, task_type: taskType, description, ...options });
  }

  getTask(taskId: string): Promise<Task> {
    return this.request("GET", `/tasks/${taskId}`);
  }

  getInbox(params?: Record<string, string>): Promise<PaginatedList<Task>> {
    return this.request("GET", "/tasks/inbox", undefined, params);
  }

  acceptTask(taskId: string): Promise<Task> {
    return this.request("POST", `/tasks/${taskId}/accept`);
  }

  declineTask(taskId: string, reason?: string): Promise<Task> {
    return this.request("POST", `/tasks/${taskId}/decline`, { reason });
  }

  completeTask(taskId: string, rating?: number, notes?: string): Promise<Task> {
    return this.request("POST", `/tasks/${taskId}/complete`, { rating, notes });
  }

  cancelTask(taskId: string, reason?: string): Promise<Task> {
    return this.request("POST", `/tasks/${taskId}/cancel`, { reason });
  }

  confirmHuman(taskId: string, token: string, confirmed = true): Promise<Task> {
    return this.request("POST", `/tasks/${taskId}/confirm-human`, { token, confirmed });
  }

  // ── Verification ──

  startEmailVerification(email: string): Promise<{ verification_id: string; status: string }> {
    return this.request("POST", "/verifications/email/start", undefined, { email });
  }

  completeEmailVerification(verificationId: string, code: string): Promise<{ verification_id: string; status: string }> {
    return this.request("POST", "/verifications/email/complete", undefined, { verification_id: verificationId, code });
  }

  startGithubVerification(): Promise<{ verification_id: string; status: string }> {
    return this.request("POST", "/verifications/github/start");
  }

  startDomainVerification(domain: string): Promise<{ verification_id: string; dns_record_value: string }> {
    return this.request("POST", "/verifications/domain/start", undefined, { domain });
  }

  completeDomainVerification(verificationId: string): Promise<{ verification_id: string; status: string }> {
    return this.request("POST", "/verifications/domain/complete", undefined, { verification_id: verificationId });
  }

  // ── Reports ──

  reportAgent(agentId: string, reasonCode: string, notes?: string): Promise<{ report_id: string; status: string }> {
    const params: Record<string, string> = { reason_code: reasonCode };
    if (notes) params.notes = notes;
    return this.request("POST", `/agents/${agentId}/report`, undefined, params);
  }

  // ── Events (SSE) ──

  async *eventStream(): AsyncGenerator<SSEvent> {
    const resp = await fetch(`${this.baseUrl}/events/stream`, {
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        Accept: "text/event-stream",
      },
    });
    if (!resp.ok) throw new Error("SSE connection failed");
    if (!resp.body) throw new Error("No response body");

    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let eventType: string | undefined;
    let dataLines: string[] = [];
    let eventId: string | undefined;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventType = line.slice(7);
        } else if (line.startsWith("data: ")) {
          dataLines.push(line.slice(6));
        } else if (line.startsWith("id: ")) {
          eventId = line.slice(4);
        } else if (line === "" && eventType) {
          const raw = dataLines.join("\n");
          let parsed: unknown;
          try { parsed = JSON.parse(raw); } catch { parsed = raw; }
          yield { event: eventType, data: parsed, id: eventId };
          eventType = undefined;
          dataLines = [];
          eventId = undefined;
        }
      }
    }
  }

  eventStatus(): Promise<{ agent_id: string; active_connections: number; is_connected: boolean }> {
    return this.request("GET", "/events/status");
  }

  // ── Self Info ──

  getMyAgent(): Promise<Agent> {
    return this.request("GET", "/agents/me");
  }

  getMyStats(): Promise<Record<string, unknown>> {
    return this.request("GET", "/agents/me/stats");
  }

  getMyActivity(params?: Record<string, string>): Promise<PaginatedList<Record<string, unknown>>> {
    return this.request("GET", "/agents/me/activity", undefined, params);
  }

  listMyVerifications(method?: string): Promise<{ data: Record<string, unknown>[] }> {
    const params: Record<string, string> = {};
    if (method) params.method = method;
    return this.request("GET", "/verifications/my", undefined, params);
  }

  // ── Public ──

  listPublicAgents(params?: Record<string, string>): Promise<PaginatedList<Agent>> {
    return this.request("GET", "/public/agents", undefined, params);
  }

  getPublicAgent(slug: string): Promise<Agent> {
    return this.request("GET", `/public/agents/${slug}`);
  }

  getPublicAgentActivity(slug: string): Promise<Record<string, unknown>> {
    return this.request("GET", `/public/agents/${slug}/activity`);
  }

  // ── Health ──

  health(): Promise<{ status: string; version: string }> {
    return this.request("GET", "/health");
  }
}
