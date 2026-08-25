/**
 * Sidebar lower rail mode — files/school expand in-place; no /more/files hub.
 */
export type PicoSidebarRail = 'chats' | 'files' | 'school';

const KEY = 'pico.sidebar.rail';
const EVENT = 'pico-sidebar-rail';

export function getPicoSidebarRail(): PicoSidebarRail {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (raw === 'files' || raw === 'school' || raw === 'chats') return raw;
  } catch {
    /* ignore */
  }
  return 'chats';
}

export function setPicoSidebarRail(rail: PicoSidebarRail) {
  try {
    sessionStorage.setItem(KEY, rail);
  } catch {
    /* ignore */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(EVENT, { detail: rail }));
  }
}

export function subscribePicoSidebarRail(listener: (rail: PicoSidebarRail) => void) {
  const onStorage = (event: Event) => {
    const detail = (event as CustomEvent<PicoSidebarRail>).detail;
    listener(detail || getPicoSidebarRail());
  };
  window.addEventListener(EVENT, onStorage);
  return () => window.removeEventListener(EVENT, onStorage);
}
