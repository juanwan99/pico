/** #1090: a quiet active run says the model is thinking, not the stale step. */
import { composeProcessHint, thinkingLine } from '~/hooks/Pico/usePicoTaskLedger';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

const running: PicoRun = { id: 'r1', task_id: 't1', status: 'running' };

function ev(seq: number, type: string, payload: Record<string, unknown> = {}): PicoRunEvent {
  return { id: `e${seq}`, run_id: 'r1', seq, type, payload };
}

const afterTool = [
  ev(1, 'tool.call', { tool: 'write' }),
  ev(2, 'tool.result', { tool: 'write' }),
  ev(3, 'agent.step', { n: 2 }),
];

describe('thinkingLine / composeProcessHint quiet stretch', () => {
  it('keeps the last step under 10s, then says thinking with seconds', () => {
    expect(composeProcessHint(running, afterTool, 9_000)).not.toMatch(/模型在思考/);
    expect(composeProcessHint(running, afterTool, 25_400)).toBe(
      '云端继续中 · 模型在思考 · 已 25 秒',
    );
  });

  it('covers a slow first token before any tool', () => {
    expect(composeProcessHint(running, [ev(1, 'run.status')], 12_000)).toBe(
      '云端继续中 · 模型在思考 · 已 12 秒',
    );
  });

  it('does not call a running tool or a pending choice thinking', () => {
    expect(thinkingLine(afterTool.slice(0, 1), 60_000)).toBeNull();
    expect(composeProcessHint(running, [ev(1, 'ui.prompt.begin')], 60_000)).not.toMatch(
      /模型在思考/,
    );
  });

  it('never says thinking once the run is over', () => {
    expect(composeProcessHint({ ...running, status: 'succeeded' }, afterTool, 60_000)).not.toMatch(
      /模型在思考/,
    );
  });
});
