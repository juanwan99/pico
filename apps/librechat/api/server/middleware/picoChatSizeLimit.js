/**
 * Pico stage #265 F1: hard-limit chat message size before heavy agent work.
 * Align with API PICO_CHAT_MAX_PROMPT_CHARS (default 100000). Reject early so
 * LibreChat never burns CPU waiting on a 300k-char model turn.
 */
const { logger } = require('@librechat/data-schemas');

const DEFAULT_MAX = 100000;

function maxChars() {
  const raw = Number(process.env.PICO_CHAT_MAX_PROMPT_CHARS || DEFAULT_MAX);
  return Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : DEFAULT_MAX;
}

function collectText(value, out) {
  if (value == null) {
    return;
  }
  if (typeof value === 'string') {
    out.push(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectText(item, out);
    }
    return;
  }
  if (typeof value === 'object') {
    if (typeof value.text === 'string') {
      out.push(value.text);
    }
    if (typeof value.content === 'string') {
      out.push(value.content);
    } else if (Array.isArray(value.content)) {
      collectText(value.content, out);
    }
    if (typeof value.message === 'string') {
      out.push(value.message);
    }
  }
}

function measureUserText(body) {
  const parts = [];
  if (!body || typeof body !== 'object') {
    return 0;
  }
  collectText(body.text, parts);
  collectText(body.message, parts);
  collectText(body.prompt, parts);
  if (Array.isArray(body.messages)) {
    for (const m of body.messages) {
      if (m && (m.role === 'user' || m.isCreatedByUser === true || m.sender === 'User')) {
        collectText(m, parts);
      }
    }
  }
  // Strip Pico ledger markers from length budget (same as API).
  const joined = parts.join('\n').replace(/【[^】]+】/g, '').trim();
  return joined.length;
}

function picoChatSizeLimit(req, res, next) {
  if (req.method !== 'POST') {
    return next();
  }
  const limit = maxChars();
  const len = measureUserText(req.body);
  if (len <= limit) {
    return next();
  }
  logger.warn(`[picoChatSizeLimit] reject len=${len} limit=${limit} path=${req.originalUrl}`);
  return res.status(413).json({
    message: `输入过长（${len} 字，上限 ${limit} 字）。请缩短问题后重试；系统不会静默截断后继续执行。`,
    code: 'prompt_too_long',
    detail: `输入过长（${len} 字，上限 ${limit} 字）。请缩短问题后重试；系统不会静默截断后继续执行。`,
  });
}

module.exports = picoChatSizeLimit;
