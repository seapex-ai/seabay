/**
 * Card validation utilities.
 *
 * Validates CardEnvelope structure, action rules, and expiry.
 */

import type { Action, CardEnvelope } from './types';

export interface ValidationResult {
  valid: boolean;
  errors: string[];
}

/**
 * Validate a card envelope structure.
 */
export function validateCard(card: CardEnvelope): ValidationResult {
  const errors: string[] = [];

  // Required fields
  if (!card.card_type) errors.push('Missing card_type');
  if (!card.card_id) errors.push('Missing card_id');
  if (!card.source || card.source !== 'seabay') errors.push('source must be "seabay"');
  if (!card.fallback_text) errors.push('Missing fallback_text');
  if (card.fallback_text && card.fallback_text.length > 2000) {
    errors.push('fallback_text exceeds 2000 character limit');
  }

  // Blocks validation
  if (!Array.isArray(card.blocks)) {
    errors.push('blocks must be an array');
  }

  // Actions validation
  if (!Array.isArray(card.actions)) {
    errors.push('actions must be an array');
  } else {
    for (const action of card.actions) {
      const actionErrors = validateAction(action, card);
      errors.push(...actionErrors);
    }
  }

  // callback_base_url must be https
  if (card.callback_base_url && !card.callback_base_url.startsWith('https://')) {
    errors.push('callback_base_url must use HTTPS');
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Validate a single action against card context.
 *
 * Critical rules:
 * - R2/R3 must use open_url, NEVER callback_button
 * - callback_base_url must be https://seabay.ai only
 */
export function validateAction(action: Action, card: CardEnvelope): string[] {
  const errors: string[] = [];

  if (!action.type) {
    errors.push('Action missing type');
    return errors;
  }

  if (!action.label) {
    errors.push('Action missing label');
  }

  // Check R2/R3 rule: risk_banner present → must use open_url
  const hasRiskBanner = card.blocks.some(
    (b) => b.type === 'risk_banner' && ['R2', 'R3'].includes((b as any).risk_level)
  );

  if (hasRiskBanner && action.type === 'callback_button') {
    errors.push(`R2/R3 cards must use open_url, not callback_button (label: ${action.label})`);
  }

  if (action.type === 'open_url') {
    if (!action.url || !action.url.startsWith('https://')) {
      errors.push('open_url action must use HTTPS URL');
    }
  }

  return errors;
}

/**
 * Check if a card has expired.
 */
export function isExpired(card: CardEnvelope): boolean {
  if (!card.expires_at) return false;
  try {
    const expiry = new Date(card.expires_at);
    return new Date() > expiry;
  } catch {
    return false;
  }
}
