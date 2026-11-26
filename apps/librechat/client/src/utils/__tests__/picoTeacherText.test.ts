import { GENERIC_RETRY, leaksToTeacher, teacherSafe } from '../picoTeacherText';

describe('picoTeacherText (owner 2026-10-14: never show model / vendor / plumbing)', () => {
  it('flags model names, vendors and relay words', () => {
    for (const bad of [
      '主渠道（gpt-5.6-sol）暂时不可用，已改用备用模型 gemini-3.8-flash 继续。',
      '未能完成：OpenAI API error (400): {"message":"Invalid request."}',
      '模型中转暂时不可用（上游 503）',
      '请配置 PICO_IMAGE_GATEWAY_URL',
      'Kimi Agent',
    ]) {
      expect(leaksToTeacher(bad)).toBe(true);
    }
  });

  it('keeps plain teacher copy', () => {
    for (const ok of ['这会儿有点忙，请稍等再发一次。', '（稍等，正在重试，第 2 次）', '运行时 · pi-true']) {
      expect(leaksToTeacher(ok)).toBe(false);
      expect(teacherSafe(ok)).toBe(ok);
    }
  });

  it('keeps Chromium network errors and still blocks environment names', () => {
    const reason = '页面打开失败：地址 https://example.invalid/（ERR_NAME_NOT_RESOLVED，无法解析域名）';
    expect(teacherSafe(reason)).toBe(reason);
    expect(teacherSafe(`${reason} OPENAI_API_KEY`)).toBe(GENERIC_RETRY);
    expect(teacherSafe(`${reason} PICO_IMAGE_GATEWAY_URL`)).toBe(GENERIC_RETRY);
  });

  it('falls back instead of leaking', () => {
    expect(teacherSafe('OpenAI API error (400)')).toBe(GENERIC_RETRY);
    expect(teacherSafe('', '本次运行未能完成')).toBe('本次运行未能完成');
  });
});
