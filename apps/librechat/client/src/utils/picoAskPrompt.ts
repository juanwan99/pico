import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

const ACTIVE_RUN = new Set(['queued', 'preparing', 'running']);

/** Last unanswered ui.prompt.begin in ledger order. */
export function liveAskEvent(events: PicoRunEvent[] | null | undefined): PicoRunEvent | null {
  let last: PicoRunEvent | null = null;
  for (const event of events || []) {
    if (event.type === 'ui.prompt.begin') {
      last = event;
    }
    if (event.type === 'ui.prompt.end') {
      last = null;
    }
  }
  return last;
}

export function askOptionLabels(payload: Record<string, unknown> | undefined): string[] {
  const raw = payload?.options;
  if (!Array.isArray(raw)) {
    return [];
  }
  return raw
    .filter((item): item is string => typeof item === 'string' && Boolean(item.trim()))
    .map((item) => item.trim())
    .slice(0, 6);
}

export function askQuestionText(payload: Record<string, unknown> | undefined): string {
  const text = payload?.text;
  if (typeof text === 'string' && text.trim()) {
    return text.trim();
  }
  return '在等你选';
}

export function liveAskForRun(
  run: PicoRun | null | undefined,
  events: PicoRunEvent[] | null | undefined,
): { question: string; options: string[] } | null {
  if (!run?.id || !ACTIVE_RUN.has(String(run.status || ''))) {
    return null;
  }
  const live = liveAskEvent(events);
  if (!live) {
    return null;
  }
  const options = askOptionLabels(live.payload);
  if (options.length < 2) {
    return null;
  }
  return { question: askQuestionText(live.payload), options };
}
