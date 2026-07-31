const LAST_TASK_ROUTE_KEY = 'pico:lastTaskRoute';
const PENDING_PROMPT_KEY = 'pico:pendingPrompt';

export function rememberTaskRoute(pathname: string, search = ''): void {
  if (!/^\/c\/[^/]+$/.test(pathname)) {
    return;
  }
  try {
    sessionStorage.setItem(LAST_TASK_ROUTE_KEY, `${pathname}${search}`);
  } catch {
    // Storage may be unavailable in hardened/private browser contexts.
  }
}

export function getTaskReturnRoute(fallback = '/c/new'): string {
  try {
    const route = sessionStorage.getItem(LAST_TASK_ROUTE_KEY);
    return route && /^\/c\/[^/]+(?:\?.*)?$/.test(route) ? route : fallback;
  } catch {
    return fallback;
  }
}

export function appendPendingPrompt(prompt: string): void {
  try {
    const current = sessionStorage.getItem(PENDING_PROMPT_KEY)?.trim();
    sessionStorage.setItem(PENDING_PROMPT_KEY, current ? `${current}\n\n${prompt}` : prompt);
  } catch {
    // Navigation still works if prefill storage is unavailable.
  }
}
