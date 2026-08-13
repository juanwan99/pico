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

export function collectPicoSearchSources(
  events: PicoRunEvent[] | null | undefined,
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
  return { searched, honestMiss: searched ? honestMiss || true : false, sources };
}
