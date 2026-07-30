/**
 * Expert/skill → preferred model + session handoff for Landing/Chat.
 */
export type PicoModelMode = 'Auto' | 'kimi-k2.6' | 'Kimi-K3' | 'pico-agent' | string;

const STORAGE = 'pico:modelMode';
const PENDING = 'pico:pendingModel';
const EXPERT_KEY = 'pico:activeExpert';

export function setPicoModelMode(mode: PicoModelMode): void {
  try {
    localStorage.setItem(STORAGE, mode);
    sessionStorage.setItem(PENDING, mode);
  } catch {
    /* ignore */
  }
}

export function getPicoModelMode(): PicoModelMode {
  try {
    return localStorage.getItem(STORAGE) || 'Auto';
  } catch {
    return 'Auto';
  }
}

export function consumePendingModel(): PicoModelMode | null {
  try {
    const m = sessionStorage.getItem(PENDING);
    if (m) {
      sessionStorage.removeItem(PENDING);
      localStorage.setItem(STORAGE, m);
      return m;
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
  if (/代码|开发|工程/.test(name)) {
    return 'pico-agent';
  }
  if (/教务|研究|分析/.test(name)) {
    return 'kimi-k2.6';
  }
  return 'kimi-k2.6';
}

export function preferredModelForSkill(skillId: string): PicoModelMode {
  if (skillId === 's3') {
    return 'pico-agent';
  }
  // multi-step heavy skills can opt into agent later
  return 'kimi-k2.6';
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
