/**
 * Teacher-visible text never names a model, a vendor or the plumbing behind it
 * (owner 2026-10-14 14:28). Mirrors services/orchestrator/pico_orchestrator/teacher_text.py.
 */
export const GENERIC_RETRY = '这次没完成，请再发一次。不是你的问题写错。';

const LEAK_RE = new RegExp(
  [
    'gpt',
    'o[134]-',
    'gemini',
    'grok',
    'claude',
    'openai',
    'anthropic',
    'google',
    'deepseek',
    'kimi',
    'moonshot',
    'qwen',
    'glm',
    'zhipu',
    'doubao',
    'siliconflow',
    'aiproxy',
    'litellm',
    'new ?api',
    'x\\.ai',
    '通义',
    '千问',
    '智谱',
    '豆包',
    '硅基',
    '文心',
    '模型',
    '主渠道',
    '渠道',
    '中转',
    '网关',
    '上游',
    '首包',
    'api ?key',
    'api error',
    'error code',
    'http ?\\d{3}',
    '(?<!\\d)(?:4[0-2]\\d|429|5\\d\\d)(?!\\d)',
  ].join('|'),
  'i',
);
const ENV_RE = /\b[A-Z][A-Z0-9]*_[A-Z0-9_]{2,}\b/;

export function leaksToTeacher(text?: string | null): boolean {
  const s = text || '';
  return LEAK_RE.test(s) || ENV_RE.test(s);
}

export function teacherSafe(text?: string | null, fallback = GENERIC_RETRY): string {
  const s = (text || '').trim();
  return !s || leaksToTeacher(s) ? fallback : s;
}
