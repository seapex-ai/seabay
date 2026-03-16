/**
 * Card system type definitions — per CardEnvelope spec.
 */

export type RenderLevel = 0 | 1 | 2;

export interface CardEnvelope {
  card_type: 'task_approval' | 'match_result';
  card_version: string;
  card_id: string;
  source: 'seabay';
  created_at: string;
  expires_at?: string;
  locale: string;
  blocks: Block[];
  actions: Action[];
  fallback_text: string;
  callback_base_url: string;
  auth_hint: string;
}

export type Block =
  | HeaderBlock
  | SectionBlock
  | DividerBlock
  | BadgeRowBlock
  | RiskBannerBlock
  | AgentSummaryBlock
  | ReasonListBlock
  | KeyValueBlock
  | ContextBlock;

export interface HeaderBlock {
  type: 'header';
  text: string;
}

export interface SectionBlock {
  type: 'section';
  text: string;
  fields?: { label: string; value: string }[];
}

export interface DividerBlock {
  type: 'divider';
}

export interface BadgeRowBlock {
  type: 'badge_row';
  badges: { type: string; label: string }[];
}

export interface RiskBannerBlock {
  type: 'risk_banner';
  risk_level: string;
  message: string;
}

export interface AgentSummaryBlock {
  type: 'agent_summary';
  agent_id: string;
  name: string;
  agent_type: string;
  verification_level: string;
  status: string;
}

export interface ReasonListBlock {
  type: 'reason_list';
  reasons: string[];
}

export interface KeyValueBlock {
  type: 'key_value';
  key: string;
  value: string;
}

export interface ContextBlock {
  type: 'context';
  text: string;
}

export type Action = CallbackAction | OpenURLAction | CopyCommandAction;

export interface CallbackAction {
  type: 'callback_button';
  label: string;
  style: 'primary' | 'danger' | 'default';
  callback_method: string;
  callback_path: string;
  callback_body: Record<string, unknown>;
  confirm?: {
    title: string;
    text: string;
    confirm_label: string;
    cancel_label: string;
  };
}

export interface OpenURLAction {
  type: 'open_url';
  label: string;
  url: string;
  style: 'primary' | 'danger' | 'default';
}

export interface CopyCommandAction {
  type: 'copy_command';
  label: string;
  text: string;
}
