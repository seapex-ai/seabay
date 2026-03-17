/**
 * Card rendering engine — converts CardEnvelope JSON to HTML/text/markdown.
 *
 * Security: All text values are HTML-escaped to prevent XSS.
 */

import type { Block, CardEnvelope, RenderLevel } from './types';

/**
 * Render a card at the specified level.
 *
 * @param card - CardEnvelope JSON object
 * @param level - 0=plain text, 1=markdown, 2=HTML
 * @returns Rendered string (text, markdown, or HTML)
 */
export function renderCard(card: CardEnvelope, level: RenderLevel = 2): string {
  switch (level) {
    case 0:
      return renderToText(card);
    case 1:
      return renderToMarkdown(card);
    case 2:
      return renderToHTML(card);
    default:
      return renderToMarkdown(card);
  }
}

/**
 * Level 0: Plain text — strips all markdown formatting.
 */
export function renderToText(card: CardEnvelope): string {
  let text = card.fallback_text || '';
  // Strip markdown
  text = text.replace(/\*\*(.*?)\*\*/g, '$1');
  text = text.replace(/_(.*?)_/g, '$1');
  text = text.replace(/`(.*?)`/g, '$1');
  return text;
}

/**
 * Level 1: Markdown — returns fallback_text as-is.
 */
export function renderToMarkdown(card: CardEnvelope): string {
  return card.fallback_text || 'No content available';
}

/**
 * Level 2: Structured HTML from blocks.
 */
export function renderToHTML(card: CardEnvelope): string {
  const parts: string[] = [];

  parts.push(`<div class="ab-card ab-card--${esc(card.card_type)}" data-card-id="${esc(card.card_id)}">`);

  // Render blocks
  for (const block of card.blocks) {
    parts.push(renderBlock(block));
  }

  // Render actions
  if (card.actions.length > 0) {
    parts.push('<div class="ab-card__actions">');
    for (const action of card.actions) {
      if (action.type === 'callback_button') {
        parts.push(
          `<button class="ab-btn ab-btn--${esc(action.style)}" ` +
          `data-method="${esc(action.callback_method)}" ` +
          `data-path="${esc(action.callback_path)}" ` +
          `data-body='${esc(JSON.stringify(action.callback_body))}'` +
          `>${esc(action.label)}</button>`
        );
      } else if (action.type === 'open_url') {
        parts.push(
          `<a class="ab-btn ab-btn--${esc(action.style)}" ` +
          `href="${esc(action.url)}" target="_blank" rel="noopener"` +
          `>${esc(action.label)}</a>`
        );
      } else if (action.type === 'copy_command') {
        parts.push(
          `<button class="ab-btn ab-btn--default ab-copy" ` +
          `data-copy="${esc(action.text)}"` +
          `>${esc(action.label)}</button>`
        );
      }
    }
    parts.push('</div>');
  }

  parts.push('</div>');
  return parts.join('\n');
}

function renderBlock(block: Block): string {
  switch (block.type) {
    case 'header':
      return `<h3 class="ab-header">${esc(block.text)}</h3>`;

    case 'section': {
      let html = `<div class="ab-section"><p>${esc(block.text)}</p>`;
      if (block.fields && block.fields.length > 0) {
        html += '<dl class="ab-fields">';
        for (const f of block.fields) {
          html += `<dt>${esc(f.label)}</dt><dd>${esc(f.value)}</dd>`;
        }
        html += '</dl>';
      }
      html += '</div>';
      return html;
    }

    case 'divider':
      return '<hr class="ab-divider" />';

    case 'badge_row':
      return (
        '<div class="ab-badges">' +
        block.badges
          .map((b) => `<span class="ab-badge ab-badge--${esc(b.type)}">${esc(b.label)}</span>`)
          .join('') +
        '</div>'
      );

    case 'risk_banner':
      return (
        `<div class="ab-risk ab-risk--${esc(block.risk_level)}">` +
        `<strong>${esc(block.risk_level)}</strong> ${esc(block.message)}</div>`
      );

    case 'agent_summary':
      return (
        `<div class="ab-agent" data-agent-id="${esc(block.agent_id)}">` +
        `<strong>${esc(block.name)}</strong>` +
        `<span class="ab-agent__type">${esc(block.agent_type)}</span>` +
        `<span class="ab-agent__status ab-status--${esc(block.status)}">${esc(block.status)}</span>` +
        '</div>'
      );

    case 'reason_list':
      return (
        '<ul class="ab-reasons">' +
        block.reasons.map((r) => `<li>${esc(r)}</li>`).join('') +
        '</ul>'
      );

    case 'key_value':
      return `<div class="ab-kv"><span class="ab-kv__key">${esc(block.key)}</span> ${esc(block.value)}</div>`;

    case 'context':
      return `<small class="ab-context">${esc(block.text)}</small>`;

    default:
      return '';
  }
}

/**
 * HTML-escape a string to prevent XSS.
 */
function esc(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
