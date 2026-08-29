/**
 * Conversation titles: first-user-turn snippet, not LLM TITLE_CONVO (#260).
 * LibreChat default is "New Chat"; Pico also used 「新对话」.
 */

const UNNAMED = new Set(['', 'New Chat', '新对话']);

export function isUnnamedConvoTitle(title?: string | null): boolean {
  return UNNAMED.has((title ?? '').trim());
}

/** Strip Pico injected 【…】 markers so the sidebar title is the teacher's words. */
export function titleFromFirstMessage(text: string, maxLen = 36): string {
  const cleaned = (text || '')
    .replace(/【[^】]+】/g, ' ')
    .replace(/请严格按该专家的方法工作。/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (!cleaned) {
    return '';
  }
  if (cleaned.length <= maxLen) {
    return cleaned;
  }
  return `${cleaned.slice(0, maxLen).trim()}…`;
}

export function persistFirstMessageTitle({
  conversationId,
  currentTitle,
  firstMessage,
  isTemporary,
  updateTitle,
}: {
  conversationId?: string | null;
  currentTitle?: string | null;
  firstMessage?: string | null;
  isTemporary?: boolean;
  updateTitle: (conversationId: string, title: string) => Promise<unknown> | unknown;
}): string | null {
  if (isTemporary) {
    return null;
  }
  if (!conversationId || conversationId === 'new') {
    return null;
  }
  if (!isUnnamedConvoTitle(currentTitle)) {
    return null;
  }
  const title = titleFromFirstMessage(firstMessage ?? '');
  if (!title) {
    return null;
  }
  void Promise.resolve(updateTitle(conversationId, title)).catch(() => {
    /* keep the local snippet even if persist lags */
  });
  return title;
}
