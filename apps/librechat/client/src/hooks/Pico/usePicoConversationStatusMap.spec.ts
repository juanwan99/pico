import { act, renderHook, waitFor } from '@testing-library/react';
import {
  buildConversationStatusMap,
  nextPollMs,
  usePicoConversationStatusMap,
} from './usePicoConversationStatusMap';
import { listPicoTasks, type PicoTask } from '~/data-provider/pico/api';

jest.mock('~/data-provider/pico/api', () => ({
  ...jest.requireActual('~/data-provider/pico/api'),
  listPicoTasks: jest.fn(),
}));

const mockedListPicoTasks = jest.mocked(listPicoTasks);

describe('buildConversationStatusMap', () => {
  it('maps conversation ids to teacher-facing labels', () => {
    const tasks: PicoTask[] = [
      {
        id: 't1',
        title: 'a',
        conversation_id: 'c1',
        latest_run: { id: 'r1', status: 'running' },
      },
      {
        id: 't2',
        title: 'b',
        conversation_id: 'c2',
        latest_run: { id: 'r2', status: 'failed' },
      },
    ];
    expect(buildConversationStatusMap(tasks)).toEqual({
      c1: '仍在处理…',
      c2: '失败',
    });
  });

  it('prefers the newest run when multiple tasks share a conversation', () => {
    const tasks: PicoTask[] = [
      {
        id: 't-old',
        title: 'done',
        conversation_id: 'c-shared',
        created_at: '2026-09-19T12:01:00Z',
        latest_run: {
          id: 'r-old',
          status: 'succeeded',
          started_at: '2026-09-19T12:01:00Z',
          ended_at: '2026-09-19T12:02:00Z',
        },
      },
      {
        id: 't-new',
        title: 'live',
        conversation_id: 'c-shared',
        created_at: '2026-09-19T12:33:00Z',
        latest_run: { id: 'r-new', status: 'running', started_at: '2026-09-19T12:33:00Z' },
      },
    ];
    expect(buildConversationStatusMap(tasks)).toEqual({ 'c-shared': '仍在处理…' });
  });

  it('shows 已完成 after a later success even if an older turn on the same chat failed', () => {
    const tasks: PicoTask[] = [
      {
        id: 't-ok',
        title: '鹈鹕骑行',
        conversation_id: 'c-zhou',
        created_at: '2026-09-19T12:33:06Z',
        latest_run: {
          id: 'r-ok',
          status: 'succeeded',
          started_at: '2026-09-19T12:33:06Z',
          ended_at: '2026-09-19T12:34:48Z',
        },
      },
      {
        id: 't-fail',
        title: '鹈鹕骑行',
        conversation_id: 'c-zhou',
        created_at: '2026-09-19T12:01:17Z',
        latest_run: {
          id: 'r-fail',
          status: 'failed',
          started_at: '2026-09-19T12:01:17Z',
          ended_at: '2026-09-19T12:02:04Z',
        },
      },
    ];
    expect(buildConversationStatusMap(tasks)).toEqual({ 'c-zhou': '已完成' });
    expect(buildConversationStatusMap([...tasks].reverse())).toEqual({ 'c-zhou': '已完成' });
  });

  it('ignores tasks without conversation binding', () => {
    expect(
      buildConversationStatusMap([
        { id: 't', title: 'x', latest_run: { id: 'r', status: 'running' } },
      ]),
    ).toEqual({});
  });
});

describe('usePicoConversationStatusMap', () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it('loads task rows and derives sidebar labels with one task-list request', async () => {
    const tasks: PicoTask[] = [
      {
        id: 'task-1',
        title: '备课任务',
        conversation_id: 'conversation-1',
        latest_run: { id: 'run-1', status: 'failed' },
      },
    ];
    mockedListPicoTasks.mockResolvedValue({ tasks });

    const { result } = renderHook(() => usePicoConversationStatusMap());

    expect(result.current.loading).toBe(true);
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.tasks).toEqual(tasks);
    expect(result.current.statusByConversationId).toEqual({ 'conversation-1': '失败' });
    expect(result.current.error).toBeNull();
    expect(mockedListPicoTasks).toHaveBeenCalledTimes(1);
  });

  it('keeps the last good task rows and exposes only a safe retry message on refresh failure', async () => {
    const tasks: PicoTask[] = [
      {
        id: 'task-1',
        title: '找回任务',
        conversation_id: 'conversation-1',
        latest_run: { id: 'run-1', status: 'running' },
      },
    ];
    mockedListPicoTasks.mockResolvedValueOnce({ tasks });

    const { result } = renderHook(() => usePicoConversationStatusMap());
    await waitFor(() => expect(result.current.tasks).toEqual(tasks));

    mockedListPicoTasks.mockRejectedValueOnce(new Error('internal stack with secret'));
    act(() => result.current.refresh());

    await waitFor(() => expect(result.current.error).toBe('任务历史暂不可用，请稍后重试'));
    expect(result.current.tasks).toEqual(tasks);
    expect(result.current.error).not.toContain('internal stack');
  });
});

describe('sidebar poll cadence (pico#1328)', () => {
  const live: PicoTask[] = [
    { id: 't1', title: 'a', conversation_id: 'c1', latest_run: { id: 'r1', status: 'running' } },
  ];
  const idle: PicoTask[] = [
    { id: 't2', title: 'b', conversation_id: 'c2', latest_run: { id: 'r2', status: 'succeeded' } },
  ];

  it('polls every 1.5 s only while a run is live and the page is visible', () => {
    expect(nextPollMs(live, false)).toBe(1_500);
    expect(nextPollMs(live, true)).toBe(20_000);
    expect(nextPollMs(idle, false)).toBe(20_000);
    expect(nextPollMs([], false)).toBe(20_000);
    // A chat sending in this window counts as live before its task shows in the list.
    expect(nextPollMs([], false, true)).toBe(1_500);
    expect(nextPollMs([], true, true)).toBe(20_000);
  });

  it('flips a live row to 已完成 on the next fast poll, then slows back down', async () => {
    jest.useFakeTimers();
    try {
      mockedListPicoTasks.mockReset();
      mockedListPicoTasks.mockResolvedValueOnce({ tasks: live }).mockResolvedValue({
        tasks: [{ ...live[0], latest_run: { id: 'r1', status: 'succeeded' } }],
      });
      const { result } = renderHook(() => usePicoConversationStatusMap());
      await waitFor(() =>
        expect(result.current.statusByConversationId).toEqual({ c1: '仍在处理…' }),
      );
      await act(async () => {
        jest.advanceTimersByTime(1_500);
      });
      await waitFor(() => expect(result.current.statusByConversationId).toEqual({ c1: '已完成' }));
      expect(mockedListPicoTasks).toHaveBeenCalledTimes(2);
      await act(async () => {
        jest.advanceTimersByTime(19_000);
      });
      expect(mockedListPicoTasks).toHaveBeenCalledTimes(2);
      await act(async () => {
        jest.advanceTimersByTime(1_000);
      });
      expect(mockedListPicoTasks).toHaveBeenCalledTimes(3);
    } finally {
      jest.useRealTimers();
    }
  });

  it('loads at once when a send starts and ends, polling fast in between', async () => {
    jest.useFakeTimers();
    try {
      mockedListPicoTasks.mockReset();
      mockedListPicoTasks.mockResolvedValue({ tasks: idle });
      const { rerender } = renderHook(
        ({ submitting }) => usePicoConversationStatusMap(true, submitting),
        { initialProps: { submitting: false } },
      );
      await waitFor(() => expect(mockedListPicoTasks).toHaveBeenCalledTimes(1));
      // Send starts: the new task is not in the list yet, so nothing but the flag says "live".
      rerender({ submitting: true });
      await waitFor(() => expect(mockedListPicoTasks).toHaveBeenCalledTimes(2));
      await act(async () => {
        jest.advanceTimersByTime(1_500);
      });
      expect(mockedListPicoTasks).toHaveBeenCalledTimes(3);
      // Send ends: load now, then back to the idle pace.
      rerender({ submitting: false });
      await waitFor(() => expect(mockedListPicoTasks).toHaveBeenCalledTimes(4));
      await act(async () => {
        jest.advanceTimersByTime(19_000);
      });
      expect(mockedListPicoTasks).toHaveBeenCalledTimes(4);
    } finally {
      jest.useRealTimers();
    }
  });
});
