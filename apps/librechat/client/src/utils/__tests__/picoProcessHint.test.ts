import {
  composeProcessHint,
  computeRunStatusLabel,
  lastProcessStep,
} from '~/hooks/Pico/usePicoTaskLedger';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

function event(type: string, payload: Record<string, unknown> = {}): PicoRunEvent {
  return { id: type, run_id: 'r1', seq: 1, type, payload };
}

describe('T-PROCESS-VISIBLE process chrome', () => {
  it('labels compaction begin/end/fail and ui wait separately', () => {
    expect(lastProcessStep([event('compaction.begin', { text: '在整理上文' })])).toBe(
      '在整理上文',
    );
    expect(lastProcessStep([event('compaction.end', { text: '已压缩' })])).toBe('已压缩');
    expect(lastProcessStep([event('compaction.failed')])).toBe('压缩失败');
    expect(lastProcessStep([event('ui.prompt.begin')])).toBe('在等你选');
  });

  it('does not paint a cancelled run as 成功', () => {
    const run = {
      id: 'r1',
      task_id: 't1',
      status: 'succeeded',
      cancel_requested: true,
    } as PicoRun;
    const hint = composeProcessHint(run, []);
    expect(hint).toMatch(/已停止/);
    expect(hint).not.toMatch(/成功/);
    expect(computeRunStatusLabel(run, false, [], [])).toBe('已停止');
  });
});
