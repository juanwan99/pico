import type { PicoRunEvent } from '~/data-provider/pico/api';

export type PicoSandboxSession = {
  sessionId: string;
  url: string;
  title: string;
  humanCopy: string;
};

const SESSION_RE = /^sbox_[A-Za-z0-9_-]{8,120}$/;
const BROWSER_TOOLS = new Set(['sandbox_browser_open', 'sandbox_browser_screenshot']);

function asSessionId(raw: unknown): string | null {
  const value = String(raw || '').trim();
  return SESSION_RE.test(value) ? value : null;
}

function parseToolResultPayload(payload: Record<string, unknown>): Record<string, unknown> | null {
  const result = payload.result;
  if (result && typeof result === 'object' && !Array.isArray(result)) {
    return result as Record<string, unknown>;
  }
  if (typeof result === 'string') {
    try {
      const parsed = JSON.parse(result) as unknown;
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        return parsed as Record<string, unknown>;
      }
    } catch {
      return null;
    }
  }
  return null;
}

function fromBody(body: Record<string, unknown> | null): PicoSandboxSession | null {
  if (!body) {
    return null;
  }
  const sessionId = asSessionId(body.session_id);
  if (!sessionId) {
    return null;
  }
  const url = String(body.url || '').trim();
  const title = String(body.title || '').trim();
  const humanCopy = String(body.human_copy || '请在此画面自行登录，不要在聊天里发送密码').trim();
  return { sessionId, url, title, humanCopy };
}

/** Latest isolated browser session from ledger events. Password fields are ignored. */
export function collectPicoSandboxSession(
  events: PicoRunEvent[] | null | undefined,
): PicoSandboxSession | null {
  let found: PicoSandboxSession | null = null;
  for (const event of events || []) {
    const payload = event.payload || {};
    if (event.type === 'sandbox.session') {
      const next = fromBody(payload);
      if (next) {
        found = next;
      }
      continue;
    }
    const tool = String(payload.tool || payload.name || '');
    if (event.type === 'tool.result' && BROWSER_TOOLS.has(tool)) {
      const next = fromBody(parseToolResultPayload(payload));
      if (next) {
        found = next;
      }
    }
  }
  return found;
}
