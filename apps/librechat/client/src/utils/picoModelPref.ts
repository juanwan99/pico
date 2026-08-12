/**
 * Expert/skill → preferred model + session handoff for Landing/Chat.
 * Dual-mode contract (#476): product surface is only pico-fast / pico-deep.
 */
export type PicoModelMode = 'pico-fast' | 'pico-deep' | string;

/** Product dual-mode options shown on Landing model chip. */
export const PICO_DUAL_MODELS: ReadonlyArray<{ id: PicoModelMode; label: string }> = [
  { id: 'pico-fast', label: 'Pico 快速' },
  { id: 'pico-deep', label: 'Pico 深度' },
];

const STORAGE = 'pico:modelMode';
const PENDING = 'pico:pendingModel';
const EXPERT_KEY = 'pico:activeExpert';

/** Map legacy SKU / Auto / display name → dual-mode id. */
export function normalizePicoModelMode(raw: string | null | undefined): PicoModelMode {
  const s = (raw || '').trim();
  if (!s || s === 'Auto') {
    return 'pico-fast';
  }
  const low = s.toLowerCase();
  if (low === 'pico-deep' || s === 'Pico 深度' || s.includes('深度')) {
    return 'pico-deep';
  }
  if (
    low === 'pico-fast' ||
    s === 'Pico 快速' ||
    s.includes('快速') ||
    low === 'pico-agent' ||
    low.startsWith('kimi') ||
    low.startsWith('moonshot') ||
    low.includes('deepseek')
  ) {
    return 'pico-fast';
  }
  return 'pico-fast';
}

export function labelForPicoModel(mode: PicoModelMode): string {
  const hit = PICO_DUAL_MODELS.find((m) => m.id === mode);
  return hit?.label ?? mode;
}

export function setPicoModelMode(mode: PicoModelMode): void {
  try {
    const id = normalizePicoModelMode(mode);
    localStorage.setItem(STORAGE, id);
    sessionStorage.setItem(PENDING, id);
  } catch {
    /* ignore */
  }
}

export function getPicoModelMode(): PicoModelMode {
  try {
    return normalizePicoModelMode(localStorage.getItem(STORAGE));
  } catch {
    return 'pico-fast';
  }
}

export function consumePendingModel(): PicoModelMode | null {
  try {
    const m = sessionStorage.getItem(PENDING);
    if (m) {
      sessionStorage.removeItem(PENDING);
      const id = normalizePicoModelMode(m);
      localStorage.setItem(STORAGE, id);
      return id;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function setActiveExpert(name: string | null): void {
  try {
    if (name) {
      sessionStorage.setItem(EXPERT_KEY, name);
    } else {
      sessionStorage.removeItem(EXPERT_KEY);
    }
  } catch {
    /* ignore */
  }
}

export function preferredModelForExpert(name: string): PicoModelMode {
  // Research/analysis → deep lane; delivery/code → fast lane.
  if (/研究|分析|深度|推理/.test(name)) {
    return 'pico-deep';
  }
  return 'pico-fast';
}

export function preferredModelForSkill(skillId: string): PicoModelMode {
  if (skillId === 'skill-chat') {
    return 'pico-fast';
  }
  // Default agentic skills stay on fast until user picks deep.
  return 'pico-fast';
}

export function expertSystemLine(): string {
  try {
    const name = sessionStorage.getItem(EXPERT_KEY);
    if (!name) {
      return '';
    }
    return `【专家角色：${name}】请严格按该专家的方法工作。\n`;
  } catch {
    return '';
  }
}
