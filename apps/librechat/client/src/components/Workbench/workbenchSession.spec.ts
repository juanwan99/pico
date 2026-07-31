import { appendPendingPrompt, getTaskReturnRoute, rememberTaskRoute } from './workbenchSession';

describe('workbenchSession', () => {
  beforeEach(() => sessionStorage.clear());

  it('remembers only task routes', () => {
    rememberTaskRoute('/c/task-42', '?view=results');
    expect(getTaskReturnRoute()).toBe('/c/task-42?view=results');

    rememberTaskRoute('/automation');
    expect(getTaskReturnRoute()).toBe('/c/task-42?view=results');
  });

  it('falls back when a stored return route is unsafe', () => {
    sessionStorage.setItem('pico:lastTaskRoute', 'https://example.com');
    expect(getTaskReturnRoute()).toBe('/c/new');
  });

  it('appends assistant and skill prefills instead of replacing either', () => {
    sessionStorage.setItem('pico:pendingPrompt', '使用 skill.read 分析附件。');
    appendPendingPrompt('请以「文档助理」的角色协助完成任务：');
    expect(sessionStorage.getItem('pico:pendingPrompt')).toBe(
      '使用 skill.read 分析附件。\n\n请以「文档助理」的角色协助完成任务：',
    );
  });
});
