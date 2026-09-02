/**
 * #461 PR-A2: after a run reaches a terminal state, the ledger must refresh
 * artifacts immediately (and on a tight 500 ms poll) so multi-file chips
 * (e.g. C2 5 files) appear without the old 4×1.5 s lag that left "1 file"
 * visible right after completion.
 */
import { renderHook, act } from '@testing-library/react';
import { ledgerPollMode, usePicoTaskLedger } from '~/hooks/Pico/usePicoTaskLedger';
import * as picoApi from '~/data-provider/pico/api';

jest.mock('~/data-provider/pico/api', () => ({
  listPicoTasks: jest.fn(),
  getPicoTask: jest.fn(),
  listPicoConversationArtifacts: jest.fn(),
  listPicoTaskRuns: jest.fn(),
  listPicoRunEvents: jest.fn(),
  cancelPicoRun: jest.fn(),
  cancelPicoTaskActiveRuns: jest.fn(),
  retryPicoRun: jest.fn(),
  rebindConversation: jest.fn(),
}));

const mockedApi = picoApi as jest.Mocked<typeof picoApi>;

const convId = 'conv-123';
const taskId = 'task-456';
const runId = 'run-789';

function terminalTask() {
  return {
    id: taskId,
    school_id: 's1',
    membership_id: 'm1',
    title: 'test task',
    conversation_id: convId,
    created_at: '2026-08-11T00:00:00Z',
  };
}

function terminalRun(status: 'succeeded' | 'failed' = 'succeeded') {
  return {
    id: runId,
    task_id: taskId,
    status,
    model: 'pico-agent',
    prompt: 'test',
    error: null,
    cancel_requested: false,
  };
}

function setupDefaults() {
  mockedApi.listPicoTasks.mockResolvedValue({ tasks: [terminalTask()] });
  mockedApi.listPicoTaskRuns.mockResolvedValue({ runs: [terminalRun()] });
  mockedApi.getPicoTask.mockResolvedValue({
    task: terminalTask(),
    artifacts: [
      { id: 'a1', kind: 'doc', title: '项目一页纸.md', user_label: '项目一页纸.md', run_id: runId },
      { id: 'a2', kind: 'csv', title: '里程碑.csv', user_label: '里程碑.csv', run_id: runId },
      { id: 'a3', kind: 'doc', title: '风险清单.md', user_label: '风险清单.md', run_id: runId },
      { id: 'a4', kind: 'doc', title: '周报模板.md', user_label: '周报模板.md', run_id: runId },
      { id: 'a5', kind: 'txt', title: '给老板的3句口头汇报.txt', user_label: '给老板的3句口头汇报.txt', run_id: runId },
    ],
  });
  mockedApi.listPicoRunEvents.mockResolvedValue({ events: [] });
  mockedApi.listPicoConversationArtifacts.mockResolvedValue({ artifacts: [] });
}

describe('ledgerPollMode', () => {
  it('polls only while submitting or the run is live', () => {
    expect(
      ledgerPollMode({ isSubmitting: true, activeRun: false, recovering: false, hasRun: false }),
    ).toBe('live');
    expect(
      ledgerPollMode({ isSubmitting: false, activeRun: true, recovering: false, hasRun: true }),
    ).toBe('live');
  });

  it('does not 2s-poll a finished chat during the recovery window', () => {
    expect(
      ledgerPollMode({ isSubmitting: false, activeRun: false, recovering: true, hasRun: true }),
    ).toBe('tail');
  });

  it('recovers only when the ledger has not bound a run yet', () => {
    expect(
      ledgerPollMode({ isSubmitting: false, activeRun: false, recovering: true, hasRun: false }),
    ).toBe('recover');
  });
});

describe('usePicoTaskLedger — terminal artifacts refresh (#461 PR-A2)', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
    mockedApi.rebindConversation.mockResolvedValue({ updated: 0, from: '', to: '' });
    setupDefaults();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  /**
   * PR-A2 makes the ledger refresh artifacts immediately after a terminal run
   * (plus a tight 500 ms poll) so multi-file chips render without the old
   * 4×1.5 s lag. This test uses real timers because React 18 + jest fake
   * timers do not reliably drive the hook's interval scheduler.
   */
  it('refreshes all artifacts shortly after a terminal run (real timers)', async () => {
    jest.useRealTimers();
    const { result } = renderHook(() => usePicoTaskLedger(convId, false));
    // initial load
    await act(async () => {
      await new Promise((r) => setTimeout(r, 150));
    });
    expect(result.current.artifacts).toHaveLength(5);

    const afterLoad = mockedApi.getPicoTask.mock.calls.length;
    await act(async () => {
      await new Promise((r) => setTimeout(r, 1600));
    });
    expect(result.current.artifacts).toHaveLength(5);
    expect(result.current.run?.status).toBe('succeeded');
    const afterTail = mockedApi.getPicoTask.mock.calls.length;
    expect(afterTail).toBeGreaterThan(afterLoad);
    await act(async () => {
      await new Promise((r) => setTimeout(r, 2500));
    });
    expect(mockedApi.getPicoTask.mock.calls.length).toBe(afterTail);
  }, 15_000);
});
