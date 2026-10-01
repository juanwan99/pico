/** #1135: a run waiting for a workspace box says where it is in line. */
import { composeProcessHint, queueLine } from '~/hooks/Pico/usePicoTaskLedger';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

const running: PicoRun = { id: 'r1', task_id: 't1', status: 'running' };

function ev(seq: number, type: string, payload: Record<string, unknown> = {}): PicoRunEvent {
  return { id: `e${seq}`, run_id: 'r1', seq, type, payload };
}

describe('queueLine / composeProcessHint while queued', () => {
  it('says how many runs are ahead, even after a long quiet', () => {
    const events = [ev(1, 'run.durable'), ev(2, 'run.queued', { ahead: 3 })];
    expect(composeProcessHint(running, events, 60_000)).toBe(
      '云端继续中 · 排队中 · 前面还有 3 个任务',
    );
  });

  it('says next up at the front of the line', () => {
    expect(queueLine([ev(1, 'run.queued', { ahead: 0 })])).toBe('排队中 · 马上轮到你');
  });

  it('stops saying queued once the run left the line', () => {
    const events = [ev(1, 'run.queued', { ahead: 1 }), ev(2, 'run.queued', { ahead: 0, started: true })];
    expect(queueLine(events)).toBeNull();
    expect(composeProcessHint(running, events, 0)).not.toMatch(/排队/);
  });

  it('is not shown once later events arrived or the run is over', () => {
    expect(queueLine([ev(1, 'run.queued', { ahead: 2 }), ev(2, 'run.model')])).toBeNull();
    expect(
      composeProcessHint({ ...running, status: 'failed' }, [ev(1, 'run.queued', { ahead: 2 })]),
    ).not.toMatch(/排队/);
  });
});
