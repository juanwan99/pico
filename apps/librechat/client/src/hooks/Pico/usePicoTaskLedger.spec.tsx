import { act, renderHook, waitFor } from '@testing-library/react';
import {
  cancelPicoRun,
  getPicoTask,
  listPicoRunEvents,
  listPicoTaskRuns,
  listPicoTasks,
  retryPicoRun,
} from '~/data-provider/pico/api';
import {
  composeProcessHint,
  computeRunStatusLabel,
  friendlyFailureLabel,
  lastProcessStep,
  mapRawRunErrorToUserMessage,
  mergePolledRun,
  pickPreferredRun,
  pickPreferredTaskRuns,
  recoveryTaskCandidates,
  usePicoTaskLedger,
} from './usePicoTaskLedger';

jest.mock('~/data-provider/pico/api', () => ({
  cancelPicoRun: jest.fn(),
  getPicoTask: jest.fn(),
  listPicoRunEvents: jest.fn(),
  listPicoTaskRuns: jest.fn(),
  listPicoTasks: jest.fn(),
  rebindConversation: jest.fn(),
  retryPicoRun: jest.fn(),
}));

const mockedListTasks = jest.mocked(listPicoTasks);
const mockedGetTask = jest.mocked(getPicoTask);
const mockedListRuns = jest.mocked(listPicoTaskRuns);
const mockedListEvents = jest.mocked(listPicoRunEvents);
const mockedCancelRun = jest.mocked(cancelPicoRun);
const mockedRetryRun = jest.mocked(retryPicoRun);

describe('workbench Chinese progress (T-AGENT-FACE-V1)', () => {
  it('labels generate_docx_document as 正在写 Word', () => {
    expect(
      lastProcessStep([
        {
          id: 'e1',
          run_id: 'r1',
          seq: 1,
          type: 'tool.call',
          payload: { tool: 'generate_docx_document' },
        },
      ]),
    ).toBe('正在写 Word');
  });

  it('falls back to 正在调工具 for unknown tools', () => {
    expect(
      lastProcessStep([
        {
          id: 'e1',
          run_id: 'r1',
          seq: 1,
          type: 'tool.call',
          payload: { tool: 'calculator' },
        },
      ]),
    ).toBe('正在调工具');
  });

  it('does not keep 正在 on a succeeded run', () => {
    const hint = composeProcessHint({ id: 'r1', task_id: 't1', status: 'succeeded' }, [
      {
        id: 'e1',
        run_id: 'r1',
        seq: 1,
        type: 'tool.call',
        payload: { tool: 'generate_docx_document' },
      },
    ]);
    expect(hint).not.toMatch(/正在/);
    expect(hint).toMatch(/成功/);
  });

  it('shows Chinese image failure on the process strip while running', () => {
    expect(
      lastProcessStep([
        {
          id: 'e1',
          run_id: 'r1',
          seq: 1,
          type: 'tool.result',
          payload: {
            tool: 'generate_image',
            ok: false,
            user_message: '出图服务未配置。请管理员在主机写入密钥后重试，不能编造图片。',
          },
        },
      ]),
    ).toMatch(/不能编造/);
  });
});

describe('search process copy (#537)', () => {
  it('labels an in-flight web_search as 正在检索', () => {
    expect(
      lastProcessStep([
        {
          id: 'e1',
          run_id: 'r1',
          seq: 1,
          type: 'tool.call',
          payload: { tool: 'web_search' },
        },
      ]),
    ).toBe('正在检索');
  });

  it('labels search.sources with a count even after later agent.step', () => {
    expect(
      lastProcessStep([
        {
          id: 'e2',
          run_id: 'r1',
          seq: 2,
          type: 'search.sources',
          payload: {
            tool: 'web_search',
            honest_miss: false,
            sources: [{ url: 'https://www.gov.cn/a' }],
          },
        },
        {
          id: 'e3',
          run_id: 'r1',
          seq: 3,
          type: 'agent.step',
          payload: { step: 2, phase: 'turn_end' },
        },
      ]),
    ).toBe('已检索 1 条来源');
  });
});

describe('failure / restart status labels (#443)', () => {
  it('maps raw owner-lost error to human Chinese with rerun CTA', () => {
    const msg = mapRawRunErrorToUserMessage('run owner was lost during API restart');
    expect(msg).toMatch(/重启|维护/);
    expect(msg).toMatch(/重新运行/);
    expect(msg.toLowerCase()).not.toContain('owner was lost');
  });

  it('prefers event user_message over raw English error', () => {
    const label = friendlyFailureLabel(
      { id: 'r1', task_id: 't1', status: 'failed', error: 'run owner was lost during API restart' },
      [
        {
          id: 'e1',
          run_id: 'r1',
          type: 'run.status',
          payload: {
            status: 'failed',
            user_message: '服务维护或重启导致本次任务中断。请点「重新运行」继续',
          },
        } as never,
      ],
    );
    expect(label.startsWith('失败：')).toBe(true);
    expect(label).toContain('重新运行');
    expect(label.toLowerCase()).not.toContain('owner was lost');
  });

  it('terminal failed wins over isSubmitting (no permanent 等待/准备)', () => {
    const label = computeRunStatusLabel(
      { id: 'r1', task_id: 't1', status: 'failed', error: 'run owner was lost during API restart' },
      true,
      [],
      [],
    );
    expect(label?.startsWith('失败：')).toBe(true);
    expect(label).not.toContain('等待');
  });

  it('terminal cancelled wins over isSubmitting', () => {
    const label = computeRunStatusLabel(
      { id: 'r1', task_id: 't1', status: 'cancelled' },
      true,
      [],
      [],
    );
    expect(label).toBe('已停止');
  });
});

describe('pickPreferredRun / pickPreferredTaskRuns', () => {
  it('does not regress an acknowledged stop when an older poll arrives', () => {
    const cancelled = { id: 'run-1', task_id: 'task-1', status: 'cancelled' };
    expect(mergePolledRun(cancelled, { id: 'run-1', task_id: 'task-1', status: 'running' })).toBe(
      cancelled,
    );

    const stopping = {
      id: 'run-2',
      task_id: 'task-1',
      status: 'running',
      cancel_requested: true,
    };
    expect(
      mergePolledRun(stopping, {
        id: 'run-2',
        task_id: 'task-1',
        status: 'running',
        cancel_requested: false,
      }),
    ).toBe(stopping);
  });

  it('prefers an active run over a newer terminal run on the same task', () => {
    const preferred = pickPreferredRun([
      { id: 'run-new', task_id: 't1', status: 'succeeded' },
      { id: 'run-old-active', task_id: 't1', status: 'running' },
    ]);
    expect(preferred?.id).toBe('run-old-active');
  });

  it('prefers a task that still has an active run over a newer terminal task', () => {
    const preferred = pickPreferredTaskRuns([
      {
        task: { id: 'task-new', title: 'newer terminal' },
        runs: [{ id: 'run-new', task_id: 'task-new', status: 'succeeded' }],
      },
      {
        task: { id: 'task-old', title: 'older active' },
        runs: [{ id: 'run-old', task_id: 'task-old', status: 'running' }],
      },
    ]);
    expect(preferred?.task.id).toBe('task-old');
    expect(preferred?.run?.id).toBe('run-old');
  });

  it('scans every task during reload recovery and keeps the tracked task afterward', () => {
    const tasks = Array.from({ length: 6 }, (_value, index) => ({
      id: `task-${index + 1}`,
      title: `task ${index + 1}`,
    }));

    expect(recoveryTaskCandidates(tasks, null, true)).toHaveLength(6);
    expect(recoveryTaskCandidates(tasks, 'task-6', false).map((task) => task.id)).toEqual([
      'task-1',
      'task-2',
      'task-3',
      'task-4',
      'task-5',
      'task-6',
    ]);
  });
});

describe('usePicoTaskLedger', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    sessionStorage.clear();
  });

  it('loads the selected historical conversation run and its timeline', async () => {
    mockedListTasks.mockResolvedValue({
      tasks: [{ id: 'task-history', title: '历史任务', conversation_id: 'conversation-history' }],
    });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-history', title: '历史任务' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-history', task_id: 'task-history', status: 'succeeded' }],
    });
    mockedListEvents.mockResolvedValue({
      events: [
        {
          id: 'event-history',
          run_id: 'run-history',
          seq: 1,
          type: 'skill.snapshot',
          payload: { id: 'research' },
        },
      ],
    });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-history', false));

    await waitFor(() => expect(result.current.run?.id).toBe('run-history'));
    expect(mockedListTasks).toHaveBeenCalledWith('conversation-history');
    expect(mockedListEvents).toHaveBeenCalledWith('run-history');
    expect(result.current.events).toHaveLength(1);
    unmount();
  });

  it('keeps an empty historical timeline as an empty state', async () => {
    mockedListTasks.mockResolvedValue({
      tasks: [{ id: 'task-empty', title: '无步骤任务' }],
    });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-empty', title: '无步骤任务' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-empty', task_id: 'task-empty', status: 'succeeded' }],
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-empty', false));

    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.events).toEqual([]);
    unmount();
  });

  it('keeps polling an active ledger run after a historical page reload', async () => {
    jest.useFakeTimers();
    mockedListTasks.mockResolvedValue({
      tasks: [{ id: 'task-active', title: '长任务', conversation_id: 'conversation-active' }],
    });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-active', title: '长任务' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-active', task_id: 'task-active', status: 'running' }],
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-active', false));

    try {
      await waitFor(() => expect(result.current.run?.status).toBe('running'));
      expect(mockedListRuns).toHaveBeenCalledTimes(1);

      for (let tick = 0; tick < 5; tick += 1) {
        await act(async () => {
          jest.advanceTimersByTime(2000);
        });
        await waitFor(() => expect(mockedListRuns).toHaveBeenCalledTimes(tick + 2));
      }
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('keeps the reload recovery window open until a delayed active task appears', async () => {
    jest.useFakeTimers();
    mockedListTasks
      .mockResolvedValueOnce({ tasks: [] })
      .mockResolvedValueOnce({ tasks: [] })
      .mockResolvedValueOnce({ tasks: [] })
      .mockResolvedValueOnce({ tasks: [] })
      .mockResolvedValueOnce({ tasks: [] })
      .mockResolvedValue({
        tasks: [{ id: 'task-delayed', title: '延迟任务' }],
      });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-delayed', title: '延迟任务' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-delayed', task_id: 'task-delayed', status: 'running' }],
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-delayed', false));

    try {
      for (let attempt = 0; attempt < 5; attempt += 1) {
        await act(async () => {
          jest.advanceTimersByTime(2000);
        });
      }
      await waitFor(() => expect(result.current.run?.id).toBe('run-delayed'));
      expect(result.current.statusLabel).toBe('等待模型响应');
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('tracks a reloaded latest active run through status changes until terminal', async () => {
    jest.useFakeTimers();
    mockedListTasks.mockResolvedValue({
      tasks: [{ id: 'task-long', title: '长任务', conversation_id: 'conversation-long' }],
    });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-long', title: '长任务' },
      artifacts: [],
    });
    mockedListEvents.mockResolvedValue({ events: [] });
    mockedListRuns
      .mockResolvedValueOnce({
        runs: [{ id: 'run-long', task_id: 'task-long', status: 'running' }],
      })
      .mockResolvedValueOnce({
        runs: [{ id: 'run-long', task_id: 'task-long', status: 'running' }],
      })
      .mockResolvedValueOnce({
        runs: [{ id: 'run-long', task_id: 'task-long', status: 'running' }],
      })
      .mockResolvedValue({
        runs: [{ id: 'run-long', task_id: 'task-long', status: 'succeeded' }],
      });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-long', false));

    try {
      await waitFor(() => expect(result.current.run?.status).toBe('running'));
      expect(result.current.statusLabel).toBe('等待模型响应');

      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListRuns).toHaveBeenCalledTimes(2));
      expect(result.current.run?.status).toBe('running');

      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListRuns).toHaveBeenCalledTimes(3));

      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(result.current.run?.status).toBe('succeeded'));
      expect(result.current.statusLabel).toBe('已完成');

      const callsAtTerminal = mockedListRuns.mock.calls.length;
      // Terminal path uses a short 1.5s × 4 tail, then must stop continuous polling.
      await act(async () => {
        jest.advanceTimersByTime(1500 * 4 + 500);
      });
      await waitFor(() =>
        expect(mockedListRuns.mock.calls.length).toBeGreaterThan(callsAtTerminal),
      );
      const callsAfterTail = mockedListRuns.mock.calls.length;

      await act(async () => {
        jest.advanceTimersByTime(10000);
      });
      expect(mockedListRuns.mock.calls.length).toBe(callsAfterTail);
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('resumes polling for queued/preparing runs after reload (isSubmitting=false)', async () => {
    jest.useFakeTimers();
    mockedListTasks.mockResolvedValue({
      tasks: [{ id: 'task-queued', title: '排队任务' }],
    });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-queued', title: '排队任务' },
      artifacts: [],
    });
    mockedListEvents.mockResolvedValue({ events: [] });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-queued', task_id: 'task-queued', status: 'queued' }],
    });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-queued', false));

    try {
      await waitFor(() => expect(result.current.run?.status).toBe('queued'));
      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListRuns).toHaveBeenCalledTimes(2));

      mockedListRuns.mockResolvedValue({
        runs: [{ id: 'run-queued', task_id: 'task-queued', status: 'preparing' }],
      });
      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(result.current.run?.status).toBe('preparing'));
      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListRuns).toHaveBeenCalledTimes(4));
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('follows a conversation active run even when a newer task is already terminal', async () => {
    jest.useFakeTimers();
    mockedListTasks.mockResolvedValue({
      tasks: [
        { id: 'task-new', title: '新任务已完成', conversation_id: 'conversation-mixed' },
        { id: 'task-2', title: '已完成 2', conversation_id: 'conversation-mixed' },
        { id: 'task-3', title: '已完成 3', conversation_id: 'conversation-mixed' },
        { id: 'task-4', title: '已完成 4', conversation_id: 'conversation-mixed' },
        { id: 'task-5', title: '已完成 5', conversation_id: 'conversation-mixed' },
        { id: 'task-old', title: '旧任务仍运行', conversation_id: 'conversation-mixed' },
      ],
    });
    mockedGetTask.mockImplementation(async (taskId: string) => ({
      task: { id: taskId, title: taskId },
      artifacts: [],
    }));
    mockedListRuns.mockImplementation(async (taskId: string) => {
      if (taskId === 'task-new') {
        return { runs: [{ id: 'run-new', task_id: 'task-new', status: 'succeeded' }] };
      }
      if (taskId !== 'task-old') {
        return { runs: [{ id: `run-${taskId}`, task_id: taskId, status: 'succeeded' }] };
      }
      return { runs: [{ id: 'run-old', task_id: 'task-old', status: 'running' }] };
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-mixed', false));

    try {
      await waitFor(() => expect(result.current.run?.id).toBe('run-old'));
      expect(result.current.task?.id).toBe('task-old');
      expect(result.current.run?.status).toBe('running');

      const runsBefore = mockedListRuns.mock.calls.length;
      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListRuns.mock.calls.length).toBeGreaterThan(runsBefore));
      expect(result.current.run?.id).toBe('run-old');
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('clears an active run when navigating to a different conversation', async () => {
    mockedListTasks.mockImplementation(async (conversationId?: string) => {
      if (conversationId === 'conversation-a') {
        return { tasks: [{ id: 'task-a', title: 'A' }] };
      }
      return { tasks: [] };
    });
    mockedGetTask.mockResolvedValue({ task: { id: 'task-a', title: 'A' }, artifacts: [] });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-a', task_id: 'task-a', status: 'running' }],
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, rerender, unmount } = renderHook(
      ({ conversationId }) => usePicoTaskLedger(conversationId, false),
      { initialProps: { conversationId: 'conversation-a' } },
    );
    await waitFor(() => expect(result.current.run?.id).toBe('run-a'));

    rerender({ conversationId: 'conversation-b' });
    await waitFor(() => expect(result.current.run).toBeNull());
    expect(result.current.task).toBeNull();
    unmount();
  });

  it('does not drop an active run when a poll briefly returns an empty task list', async () => {
    jest.useFakeTimers();
    mockedListTasks
      .mockResolvedValueOnce({
        tasks: [{ id: 'task-sticky', title: '粘性活跃', conversation_id: 'conversation-sticky' }],
      })
      .mockResolvedValue({ tasks: [] });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-sticky', title: '粘性活跃' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [{ id: 'run-sticky', task_id: 'task-sticky', status: 'running' }],
    });
    mockedListEvents.mockResolvedValue({ events: [] });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-sticky', false));

    try {
      await waitFor(() => expect(result.current.run?.status).toBe('running'));

      await act(async () => {
        jest.advanceTimersByTime(2000);
      });
      await waitFor(() => expect(mockedListTasks.mock.calls.length).toBeGreaterThanOrEqual(2));
      expect(result.current.run?.id).toBe('run-sticky');
      expect(result.current.run?.status).toBe('running');
    } finally {
      unmount();
      jest.useRealTimers();
    }
  });

  it('cancels a running historical run and refreshes its terminal state', async () => {
    mockedListTasks.mockResolvedValue({ tasks: [{ id: 'task-running', title: '运行中任务' }] });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-running', title: '运行中任务' },
      artifacts: [],
    });
    mockedListRuns
      .mockResolvedValueOnce({
        runs: [{ id: 'run-running', task_id: 'task-running', status: 'running' }],
      })
      .mockResolvedValue({
        runs: [{ id: 'run-running', task_id: 'task-running', status: 'cancelled' }],
      });
    mockedListEvents.mockResolvedValue({ events: [] });
    mockedCancelRun.mockResolvedValue({
      run: { id: 'run-running', task_id: 'task-running', status: 'cancelled' },
    });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-running', false));
    await waitFor(() => expect(result.current.run?.status).toBe('running'));

    await act(async () => result.current.cancelRun());

    expect(mockedCancelRun).toHaveBeenCalledWith('run-running');
    await waitFor(() => expect(result.current.run?.status).toBe('cancelled'));
    expect(result.current.statusLabel).toBe('已停止');
    unmount();
  });

  it('retries a failed run as a distinct queued ledger run', async () => {
    mockedListTasks.mockResolvedValue({ tasks: [{ id: 'task-failed', title: '失败任务' }] });
    mockedGetTask.mockResolvedValue({
      task: { id: 'task-failed', title: '失败任务' },
      artifacts: [],
    });
    mockedListRuns.mockResolvedValue({
      runs: [
        {
          id: 'run-failed',
          task_id: 'task-failed',
          status: 'failed',
          error: 'provider unavailable',
        },
      ],
    });
    mockedListEvents.mockResolvedValue({ events: [] });
    mockedRetryRun.mockResolvedValue({
      run: { id: 'run-retry', task_id: 'task-failed', status: 'queued' },
      retried_from_run_id: 'run-failed',
    });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-failed', false));
    await waitFor(() => expect(result.current.run?.status).toBe('failed'));
    mockedListRuns.mockResolvedValue({
      runs: [
        { id: 'run-retry', task_id: 'task-failed', status: 'queued' },
        { id: 'run-failed', task_id: 'task-failed', status: 'failed' },
      ],
    });

    await act(async () => result.current.rerunFailedRun());

    expect(mockedRetryRun).toHaveBeenCalledWith('run-failed');
    expect(result.current.run).toMatchObject({ id: 'run-retry', status: 'queued' });
    expect(result.current.statusLabel).toBe('等待模型响应');
    unmount();
  });

  it('cancels the run rendered by the button even if polling has replaced ledger state', async () => {
    mockedListTasks.mockResolvedValue({ tasks: [] });
    mockedCancelRun.mockResolvedValue({
      run: { id: 'run-rendered', task_id: 'task-running', status: 'cancelled' },
    });

    const { result, unmount } = renderHook(() => usePicoTaskLedger('conversation-running', false));
    await waitFor(() => expect(result.current.loading).toBe(false));

    await act(async () => result.current.cancelRun('run-rendered'));

    expect(mockedCancelRun).toHaveBeenCalledWith('run-rendered');
    unmount();
  });
});
