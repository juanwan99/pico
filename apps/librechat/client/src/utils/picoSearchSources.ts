import type { PicoRunEvent } from '~/data-provider/pico/api';

export type PicoSearchSource = {
  title: string;
  url: string;
  snippet?: string;
};

export type PicoSearchSourceView = {
  searched: boolean;
  honestMiss: boolean;
  sources: PicoSearchSource[];
};

const SEARCH_TOOLS = new Set(['web_search', 'web_fetch']);

function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

function asSource(raw: unknown): PicoSearchSource | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }
  const item = raw as { title?: unknown; url?: unknown; link?: unknown; snippet?: unknown };
  const url = String(item.url || item.link || '').trim();
  if (!url || !isHttpUrl(url)) {
    return null;
  }
  const title = String(item.title || url).trim() || url;
  const snippet = String(item.snippet || '').trim();
  return { title, url, snippet: snippet || undefined };
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

function pushSources(into: PicoSearchSource[], raw: unknown) {
  if (!Array.isArray(raw)) {
    return;
  }
  const seen = new Set(into.map((item) => item.url));
  for (const entry of raw) {
    const source = asSource(entry);
    if (!source || seen.has(source.url)) {
      continue;
    }
    seen.add(source.url);
    into.push(source);
  }
}

/** Assistant bubble text only — never invent URLs, never use user-turn text. */
export type PicoSourceMessage = {
  text?: unknown;
  content?: unknown;
  isCreatedByUser?: boolean;
};

function messageTexts(messages: PicoSourceMessage[] | null | undefined): string[] {
  const out: string[] = [];
  for (const message of messages || []) {
    if (message.isCreatedByUser) {
      continue;
    }
    if (typeof message.text === 'string' && message.text.trim()) {
      out.push(message.text);
    }
    if (typeof message.content === 'string' && message.content.trim()) {
      out.push(message.content);
    }
    if (Array.isArray(message.content)) {
      for (const part of message.content) {
        if (typeof part === 'string' && part.trim()) {
          out.push(part);
          continue;
        }
        if (part && typeof part === 'object') {
          const text = (part as { text?: unknown }).text;
          if (typeof text === 'string' && text.trim()) {
            out.push(text);
          }
        }
      }
    }
  }
  return out;
}

function sourcesFromAssistantText(text: string): PicoSearchSource[] {
  const found: PicoSearchSource[] = [];
  const seen = new Set<string>();
  const mdLink = /\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/gi;
  let match: RegExpExecArray | null;
  while ((match = mdLink.exec(text)) !== null) {
    const url = match[2].trim();
    if (!isHttpUrl(url) || seen.has(url)) {
      continue;
    }
    seen.add(url);
    const title = (match[1] || '').trim() || url;
    found.push({ title, url });
  }
  const bare = /https?:\/\/[^\s)\]>'"]+/gi;
  while ((match = bare.exec(text)) !== null) {
    const url = match[0].replace(/[.,;:]+$/, '');
    if (!isHttpUrl(url) || seen.has(url)) {
      continue;
    }
    seen.add(url);
    found.push({ title: url, url });
  }
  return found;
}

export function collectPicoSearchSources(
  events: PicoRunEvent[] | null | undefined,
  messages?: PicoSourceMessage[] | null,
): PicoSearchSourceView {
  const sources: PicoSearchSource[] = [];
  let searched = false;
  let honestMiss = false;

  for (const event of events || []) {
    const payload = event.payload || {};
    const tool = String(payload.tool || payload.name || '');
    if (event.type === 'search.sources') {
      searched = true;
      if (payload.honest_miss === true) {
        honestMiss = true;
      }
      pushSources(sources, payload.sources);
      continue;
    }
    if (event.type === 'tool.result' && SEARCH_TOOLS.has(tool)) {
      searched = true;
      const body = parseToolResultPayload(payload);
      if (body) {
        if (body.honest_miss === true) {
          honestMiss = true;
        }
        pushSources(sources, body.sources);
      }
    }
  }

  if (sources.length > 0) {
    return { searched: true, honestMiss: false, sources };
  }
  // Ledger said the search ran and missed — do not promote bubble links
  // (model may have invented citations). Honest miss wins.
  if (searched) {
    return { searched: true, honestMiss: honestMiss || true, sources };
  }
  for (const text of messageTexts(messages)) {
    pushSources(sources, sourcesFromAssistantText(text));
  }
  if (sources.length > 0) {
    return { searched: true, honestMiss: false, sources };
  }
  return { searched: false, honestMiss: false, sources };
}
