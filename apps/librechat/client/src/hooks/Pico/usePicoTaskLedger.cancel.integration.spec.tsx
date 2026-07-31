import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import TaskRunBar from '~/components/Chat/TaskRunBar';
import { usePicoTaskLedger } from './usePicoTaskLedger';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock(
  'librechat-data-provider',
  () => ({
    getTokenHeader: jest.fn(() => 'Bearer test-token'),
  }),
  { virtual: true },
);

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
    text: async () => JSON.stringify(body),
  } as Response;
}

function ledgerResponse(url: string, status = 'running'): Response {
  if (url.includes('/v1/tasks?')) {
    return response({ tasks: [{ id: 'task-live', title: '运行中任务' }] });
  }
  if (url.endsWith('/v1/tasks/task-live')) {
    return response({ task: { id: 'task-live', title: '运行中任务' }, artifacts: [] });
  }
  if (url.endsWith('/v1/tasks/task-live/runs')) {
    return response({ runs: [{ id: 'run-live', task_id: 'task-live', status }] });
  }
  if (url.endsWith('/v1/runs/run-live/events')) {
    return response({ events: [] });
  }
  throw new Error(`unexpected request: ${url}`);
}

let refreshLedger: () => void = () => undefined;

function CancelHarness() {
  const ledger = usePicoTaskLedger('conversation-live', false);
  refreshLedger = ledger.refresh;
  const runId = ['queued', 'running', 'preparing'].includes(ledger.run?.status || '')
    ? ledger.run?.id
    : undefined;
  const completedLabel =
    ledger.statusLabel &&
    (ledger.statusLabel.startsWith('已完成') ||
      ledger.statusLabel.startsWith('失败') ||
      ledger.statusLabel.startsWith('已取消'))
      ? ledger.statusLabel
      : null;

  return (
    <>
      <TaskRunBar
        title={ledger.task?.title}
        isSubmitting={false}
        statusLabel={ledger.statusLabel}
        completedLabel={completedLabel}
        canCancel={Boolean(runId)}
        cancelling={ledger.cancelling}
        onCancel={() => void ledger.cancelRun(runId)}
      />
      {ledger.error ? <div role="alert">{ledger.error}</div> : null}
    </>
  );
}

describe('Pico cancel button integration', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('clicks the rendered stop button, sends the exact POST, and shows cancelled', async () => {
    let runStatus = 'running';
    let resolveCancel!: (value: Response) => void;
    const cancelResponse = new Promise<Response>((resolve) => {
      resolveCancel = resolve;
    });
    const fetchMock = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/pico/v1/runs/run-live/cancel')) {
        expect(init?.method).toBe('POST');
        return cancelResponse;
      }
      return Promise.resolve(ledgerResponse(url, runStatus));
    });
    global.fetch = fetchMock as typeof fetch;

    render(<CancelHarness />);
    fireEvent.click(await screen.findByRole('button', { name: '停止' }));

    expect(screen.getByRole('button', { name: '停止中' })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/runs/run-live/cancel',
      expect.objectContaining({
        credentials: 'include',
        method: 'POST',
      }),
    );

    runStatus = 'cancelled';
    resolveCancel(response({ run: { id: 'run-live', task_id: 'task-live', status: 'cancelled' } }));

    expect(await screen.findByText('已取消')).toBeInTheDocument();
  });

  it('keeps a failed cancellation visible while ledger polling continues', async () => {
    const fetchMock = jest.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith('/api/pico/v1/runs/run-live/cancel')) {
        return Promise.resolve(response({ error: 'pico_upstream_unavailable' }, 502));
      }
      return Promise.resolve(ledgerResponse(url));
    });
    global.fetch = fetchMock as typeof fetch;

    render(<CancelHarness />);
    fireEvent.click(await screen.findByRole('button', { name: '停止' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('停止运行失败：账本服务暂时不可用，请稍后重试');
    const callsBeforeRefresh = fetchMock.mock.calls.length;

    act(() => refreshLedger());
    await waitFor(() => expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRefresh));
    expect(screen.getByRole('alert')).toHaveTextContent(
      '停止运行失败：账本服务暂时不可用，请稍后重试',
    );
  });
});
