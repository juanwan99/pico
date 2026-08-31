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
const PLAN_STORAGE = 'pico:planOn';

/** Map legacy SKU / Auto / display name → dual-mode id. */
export function normalizePicoModelMode(raw: string | null | undefined): PicoModelMode {
  const s = (raw || '').trim();
  if (!s || s === 'Auto') {
    return 'pico-fast';
  }
  const low = s.toLowerCase();
  // Reasoner / 深度 first — `deepseek-reasoner` also contains "deepseek".
  if (
    low === 'pico-deep' ||
    s === 'Pico 深度' ||
    s.includes('深度') ||
    low.includes('reasoner')
  ) {
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

/** Persist the lane. Must NOT write PENDING — that re-arms Landing's mount
 *  consume and, with an unstable chatCtx, loops into React #185. */
export function setPicoModelMode(mode: PicoModelMode): void {
  try {
    localStorage.setItem(STORAGE, normalizePicoModelMode(mode));
  } catch {
    /* ignore */
  }
}

/** Hub/assistant → /c/new handoff only. Landing consumePendingModel reads this once. */
export function queuePendingModel(mode: PicoModelMode): void {
  try {
    const id = normalizePicoModelMode(mode);
    localStorage.setItem(STORAGE, id);
    sessionStorage.setItem(PENDING, id);
  } catch {
    /* ignore */
  }
}

/** Keep Recoil identity when the lane is already set (avoids a new convo object). */
export function patchConversationModel<
  T extends { endpoint?: string | null; model?: string | null },
>(prev: T | null | undefined, raw: string): T | null | undefined {
  if (!prev) {
    return prev;
  }
  const id = normalizePicoModelMode(raw);
  const endpoint = prev.endpoint ?? 'openAI';
  if (prev.model === id && (prev.endpoint ?? 'openAI') === endpoint) {
    return prev;
  }
  return { ...prev, endpoint, model: id };
}

export function getPicoPlanOn(): boolean {
  try {
    return localStorage.getItem(PLAN_STORAGE) === '1';
  } catch {
    return false;
  }
}

export function setPicoPlanOn(on: boolean): void {
  try {
    localStorage.setItem(PLAN_STORAGE, on ? '1' : '0');
  } catch {
    /* ignore */
  }
}

export function patchConversationPlan<T extends { pico_plan?: boolean | null }>(
  prev: T | null | undefined,
  on: boolean,
): T | null | undefined {
  if (!prev) {
    return prev;
  }
  if (Boolean(prev.pico_plan) === Boolean(on)) {
    return prev;
  }
  return { ...prev, pico_plan: on };
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
