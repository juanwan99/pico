/**
 * Teacher-facing labels. Vendor ids (OpenAI / GPT / Gemini / Grok) stay internal.
 */

const VENDOR = /^(openai|assistant|chatgpt|gpt-\S*|gemini\S*|grok\S*|deepseek\S*|claude\S*|pico-fast|pico-deep)$/i;

export function picoAssistantLabel(raw?: string | null): string {
  const s = (raw || '').trim();
  if (!s || VENDOR.test(s) || s.toLowerCase().includes('open ai')) {
    return 'Pico';
  }
  return s;
}

const SKILL_FACE: Record<string, { title: string; desc: string }> = {
  'skill-quiz-draft': { title: '出测验草稿', desc: '根据已有材料起草结构化测验并保存。' },
  'skill-translate': { title: '翻译', desc: '翻译内容，需要时保存译文。' },
  'skill-lesson-outline': { title: '教案提纲', desc: '起草结构化教案提纲，可选保存。' },
  'skill-summarize': { title: '摘要', desc: '归纳材料要点，可选保存。' },
  'skill-meeting-notes': { title: '会议纪要', desc: '把会议内容整理成纪要，可选保存。' },
  'skill-kb-ask': { title: '问学校材料', desc: '只根据已挂材料作答，没有就不编。' },
  'skill-write-s7': { title: '改页确认', desc: '需要老师确认的改页走现有确认路径。' },
  'skill-read': { title: '读材料', desc: '阅读工作区或学校材料，不写入。' },
  'skill-chat': { title: '闲聊', desc: '只对话，不调用工具。' },
};

function looksLikeSlug(s: string): boolean {
  return /^[a-z0-9]+(?:-[a-z0-9]+)+$/i.test(s);
}

export function picoSkillTitle(skill: { name?: string; displayTitle?: string }): string {
  const name = (skill.name || '').trim();
  const shown = (skill.displayTitle || '').trim();
  if (shown && !looksLikeSlug(shown) && /[\u4e00-\u9fff]/.test(shown)) {
    return shown;
  }
  const hit = SKILL_FACE[name] || (shown ? SKILL_FACE[shown] : undefined);
  if (hit) {
    return hit.title;
  }
  if (shown && !looksLikeSlug(shown)) {
    return shown;
  }
  return name || '技能';
}

export function picoSkillDesc(skill: { name?: string; description?: string }): string | undefined {
  const name = (skill.name || '').trim();
  const desc = (skill.description || '').trim();
  const hit = SKILL_FACE[name];
  if (hit && (!desc || !/[\u4e00-\u9fff]/.test(desc))) {
    return hit.desc;
  }
  return desc || hit?.desc;
}
