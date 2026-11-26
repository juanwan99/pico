import { stripPicoControlMarkers } from '../picoControlMarkers';

describe('stripPicoControlMarkers', () => {
  const body = '打开 https://example.com。\n\n然后读【操作说明】。';

  it.each([
    '【Pico-User:u1】',
    '【Pico-Convo:pending_x】',
    '【Pico-Skill:skill-docs】',
    '【工作空间：甲】',
    '【工作空间：甲】（备注）',
    '【权限：默认沙箱】',
    '【模型偏好：pico-deep】',
    '【项目指令：先读说明】',
  ])('strips %s and preserves the message body', (marker) => {
    expect(stripPicoControlMarkers(`${marker}\n${body}`)).toBe(body);
  });

  it('trims surrounding whitespace and keeps ordinary text intact', () => {
    expect(stripPicoControlMarkers(`  \n${body}\n  `)).toBe(body);
  });
});
