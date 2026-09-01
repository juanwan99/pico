import { askOptionLabels, isAskUserWaiting, liveAskEvent, liveAskForRun } from '../picoAskPrompt';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

function event(id: string, seq: number, type: string, payload: Record<string, unknown> = {}): PicoRunEvent {
  return { id, run_id: 'run-1', seq, type, payload };
}

function run(status: string): PicoRun {
  return { id: 'run-1', task_id: 'task-1', status };
}

describe('picoAskPrompt', () => {
  it('tracks the open ui.prompt.begin until end', () => {
    expect(
      liveAskEvent([
        event('a', 1, 'ui.prompt.begin', { text: 'one', options: ['A', 'B'] }),
        event('b', 2, 'ui.prompt.end', { text: '已选' }),
        event('c', 3, 'ui.prompt.begin', { text: 'two', options: ['确认执行', '先不执行', '再改计划'] }),
      ])?.id,
    ).toBe('c');
    expect(
      liveAskEvent([
        event('a', 1, 'ui.prompt.begin', { options: ['A', 'B'] }),
        event('b', 2, 'ui.prompt.end', {}),
      ]),
    ).toBeNull();
  });

  it('keeps at most six trimmed option labels', () => {
    expect(
      askOptionLabels({
        options: [' 确认执行 ', '', '先不执行', 3, '再改计划', '四', '五', '六', '七'],
      }),
    ).toEqual(['确认执行', '先不执行', '再改计划', '四', '五', '六']);
  });

  it('exposes a main-column ask only on a live running run with ≥2 options', () => {
    const events = [
      event('wait', 1, 'ui.prompt.begin', {
        text: '计划好了，下一步？',
        options: ['确认执行', '先不执行', '再改计划'],
      }),
    ];
    expect(liveAskForRun(run('running'), events)).toEqual({
      question: '计划好了，下一步？',
      options: ['确认执行', '先不执行', '再改计划'],
    });
    expect(liveAskForRun(run('succeeded'), events)).toBeNull();
    expect(liveAskForRun(run('running'), [event('wait', 1, 'ui.prompt.begin', { text: 'x' })])).toBeNull();
  });

  it('treats an open ui.prompt.begin on an active run as waiting for a pick', () => {
    const events = [event('wait', 1, 'ui.prompt.begin', { text: '在等你选', options: ['A', 'B'] })];
    expect(isAskUserWaiting(run('running'), events)).toBe(true);
    expect(isAskUserWaiting(run('succeeded'), events)).toBe(false);
    expect(isAskUserWaiting(run('running'), [])).toBe(false);
  });
});
