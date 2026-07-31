import { act, renderHook, waitFor } from '@testing-library/react';
import {
  cancelPicoRun,
  getPicoTask,
  listPicoRunEvents,
  listPicoTaskRuns,
  listPicoTasks,
} from '~/data-provider/pico/api';
import { usePicoTaskLedger } from './usePicoTaskLedger';

jest.mock('~/data-provider/pico/api', () => ({
  cancelPicoRun: jest.fn(),
  getPicoTask: jest.fn(),
  listPicoRunEvents: jest.fn(),
  listPicoTaskRuns: jest.fn(),
  listPicoTasks: jest.fn(),
  rebindConversation: jest.fn(),
}));

const mockedListTasks = jest.mocked(listPicoTasks);
const mockedGetTask = jest.mocked(getPicoTask);
const mockedListRuns = jest.mocked(listPicoTaskRuns);
const mockedListEvents = jest.mocked(listPicoRunEvents);
const mockedCancelRun = jest.mocked(cancelPicoRun);

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

    const { result, unmount } = renderHook(() =>
      usePicoTaskLedger('conversation-history', false),
    );

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
    expect(result.current.statusLabel).toBe('已取消');
    unmount();
  });
});
