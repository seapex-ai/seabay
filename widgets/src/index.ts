/**
 * Seabay V1.5 — Embeddable Widget Rendering Engine
 *
 * Renders CardEnvelope JSON into HTML for embedding in host applications.
 * Supports 3 render levels:
 *   0 = plain text (strip markdown)
 *   1 = markdown fallback
 *   2 = structured HTML from blocks
 */

export { renderCard, renderToHTML, renderToText, renderToMarkdown } from './renderer';
export { validateCard, validateAction, isExpired } from './validator';
export type {
  CardEnvelope,
  Block,
  Action,
  CallbackAction,
  OpenURLAction,
  CopyCommandAction,
  RenderLevel,
} from './types';
