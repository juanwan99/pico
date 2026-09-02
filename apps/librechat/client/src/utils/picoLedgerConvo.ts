import { Constants } from 'librechat-data-provider';

function isSavedConversationId(id?: string | null): id is string {
  const value = (id || '').trim();
  return Boolean(
    value &&
      value !== Constants.NEW_CONVO &&
      value !== Constants.SEARCH &&
      !value.startsWith('pending_'),
  );
}

/**
 * PicoAskBar reads the ledger by conversation id. The first turn stays on
 * `/c/new` until SSE final; Recoil already has the saved id from `created`.
 * Bind the ledger to that saved id so a parked ask_user is clickable.
 */
export function resolveLedgerConversationId(
  routeId?: string | null,
  liveId?: string | null,
): string | undefined {
  const route = (routeId || '').trim();
  if (route === Constants.SEARCH) {
    return route;
  }
  if (isSavedConversationId(routeId)) {
    return route;
  }
  if (isSavedConversationId(liveId)) {
    return liveId.trim();
  }
  const live = (liveId || '').trim();
  return route || live || undefined;
}
