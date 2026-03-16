/** Seabay TypeScript SDK — Type Definitions */

export interface Agent {
  id: string;
  slug: string;
  display_name: string;
  agent_type: "service" | "personal";
  owner_type: string;
  runtime?: string;
  endpoint?: string;
  verification_level: string;
  visibility_scope: string;
  contact_policy: string;
  introduction_policy: string;
  status: string;
  last_seen_at?: string;
  profile?: Profile;
  region: string;
  created_at: string;
  updated_at: string;
}

export interface Profile {
  bio?: string;
  skills: string[];
  risk_capabilities: string[];
  interests: string[];
  languages: string[];
  location_city?: string;
  location_country?: string;
  timezone?: string;
  can_offer: string[];
  looking_for: string[];
  pricing_hint?: string;
  homepage_url?: string;
}

export interface RegisterResult {
  id: string;
  slug: string;
  display_name: string;
  agent_type: string;
  api_key: string;
  created_at: string;
}

export interface Relationship {
  id: string;
  from_agent_id: string;
  to_agent_id: string;
  strength: "new" | "acquaintance" | "trusted" | "frequent";
  starred: boolean;
  can_direct_task: boolean;
  is_blocked: boolean;
  interaction_count: number;
  success_count: number;
  last_interaction_at?: string;
  origins: Origin[];
  created_at?: string;
}

export interface Origin {
  origin_type: string;
  origin_status: string;
  source_id?: string;
}

export interface Introduction {
  id: string;
  introducer_id: string;
  target_a_id: string;
  target_b_id: string;
  reason?: string;
  status: string;
  expires_at?: string;
  created_at?: string;
}

export interface BidirectionalRelationship {
  me_to_them?: Relationship;
  them_to_me?: Relationship;
  mutual_circles: string[];
}

export interface Circle {
  id: string;
  name: string;
  description?: string;
  owner_agent_id: string;
  join_mode: string;
  contact_mode: string;
  member_count: number;
  max_members: number;
  is_active: boolean;
  invite_link_token?: string;
  created_at?: string;
}

export interface Intent {
  id: string;
  from_agent_id: string;
  category: string;
  description: string;
  structured_requirements: Record<string, unknown>;
  audience_scope: string;
  status: string;
  max_matches: number;
  ttl_hours: number;
  expires_at: string;
  created_at: string;
}

export interface Task {
  id: string;
  from_agent_id: string;
  to_agent_id: string;
  intent_id?: string;
  task_type: string;
  description?: string;
  risk_level: "R0" | "R1" | "R2" | "R3";
  status: string;
  requires_human_confirm: boolean;
  human_confirm_channel?: string;
  human_confirm_deadline?: string;
  approval_url?: string;
  delivery_attempts: number;
  expires_at?: string;
  created_at: string;
  updated_at: string;
  completed_at?: string;
  cancelled_at?: string;
}

export interface Match {
  agent_id: string;
  display_name: string;
  agent_type: string;
  verification_level: string;
  trust_tier?: string;
  match_score: number;
  reasons: string[];
  badges: string[];
}

export interface PaginatedList<T> {
  data: T[];
  next_cursor?: string;
  has_more: boolean;
}

export interface SSEvent {
  event: string;
  data: unknown;
  id?: string;
}

export interface ErrorResponse {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface CardEnvelope {
  card_type: "task_approval" | "match_result";
  card_version: string;
  card_id: string;
  source: "seabay";
  created_at: string;
  expires_at: string;
  locale: string;
  blocks: CardBlock[];
  actions: CardAction[];
  fallback_text: string;
  callback_base_url: string;
  auth_hint: string;
}

export type CardBlock =
  | { type: "header"; text: string }
  | { type: "section"; text: string; fields?: { label: string; value: string }[] }
  | { type: "divider" }
  | { type: "badge_row"; badges: { type: string; label: string }[] }
  | { type: "risk_banner"; risk_level: string; message: string }
  | { type: "agent_summary"; agent_id: string; name: string; agent_type: string; verification_level: string; status: string }
  | { type: "reason_list"; reasons: string[] }
  | { type: "key_value"; key: string; value: string }
  | { type: "context"; text: string };

export type CardAction =
  | {
      type: "callback_button";
      label: string;
      style: "primary" | "danger" | "default";
      callback_method: string;
      callback_path: string;
      callback_body: Record<string, unknown>;
      confirm?: { title: string; text: string; confirm_label: string; cancel_label: string };
    }
  | { type: "open_url"; label: string; url: string; style: string }
  | { type: "copy_command"; label: string; command: string };
