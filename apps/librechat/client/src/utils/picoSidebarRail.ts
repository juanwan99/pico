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

export function isChatPath(pathname: string): boolean {
  return pathname === '/c' || pathname.startsWith('/c/');
}

/** Exactly one of 搜索 / 技能与连接器 / 我的文件 / 学校材料. */
export function isPicoNavItemActive(
  pathname: string,
  itemId: string,
  rail: PicoSidebarRail,
): boolean {
  if (itemId === 'files') {
    return rail === 'files';
  }
  if (itemId === 'school') {
    return rail === 'school';
  }
  if (rail === 'files' || rail === 'school') {
    return false;
  }
  if (itemId === 'capability') {
    return pathname.startsWith('/capability') || pathname.startsWith('/skills');
  }
  if (itemId === 'search') {
    return pathname.startsWith('/search');
  }
  return false;
}
