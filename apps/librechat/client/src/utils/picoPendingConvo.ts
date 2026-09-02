/**
 * Draft conversation id for /c/new uploads and the first send.
 * LibreChat has no real id yet; Pico already rebinds pending_* → real id.
 * Do not invent a second file matcher — bind explicitly.
 */
const KEY = 'pico:pendingConvo';

export function peekPendingConvoId(): string | null {
  try {
    const value = sessionStorage.getItem(KEY);
    return value && value.startsWith('pending_') ? value : null;
  } catch {
    return null;
  }
}

export function ensurePendingConvoId(): string {
  const existing = peekPendingConvoId();
  if (existing) {
    return existing;
  }
  const id =
    typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
      ? `pending_${crypto.randomUUID()}`
      : `pending_${Date.now()}`;
  try {
    sessionStorage.setItem(KEY, id);
  } catch {
    /* private mode: still return a stable id for this caller's stack */
  }
  return id;
}

export function markPendingRebind(realId: string): void {
  const pending = peekPendingConvoId();
  const to = String(realId || '').trim();
  if (!pending || !to || pending === to || to === 'new') {
    return;
  }
  try {
    sessionStorage.setItem('pico:rebindFrom', pending);
    sessionStorage.setItem('pico:rebindTo', to);
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}
