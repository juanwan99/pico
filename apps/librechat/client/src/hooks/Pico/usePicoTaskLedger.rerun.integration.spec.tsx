import { fireEvent, render, screen } from '@testing-library/react';
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

function ledgerResponse(url: string, retried: boolean): Response {
  if (url.includes('/v1/tasks?')) {
    return response({ tasks: [{ id: 'task-failed', title: '失败任务' }] });
  }
  if (url.endsWith('/v1/tasks/task-failed')) {
    return response({ task: { id: 'task-failed', title: '失败任务' }, artifacts: [] });
  }
  if (url.endsWith('/v1/tasks/task-failed/runs')) {
    return response({
      runs: retried
        ? [
            { id: 'run-retry', task_id: 'task-failed', status: 'queued' },
            {
              id: 'run-failed',
              task_id: 'task-failed',
              status: 'failed',
              error: 'provider unavailable',
            },
          ]
        : [
            {
              id: 'run-failed',
              task_id: 'task-failed',
              status: 'failed',
              error: 'provider unavailable',
            },
          ],
    });
  }
  if (url.endsWith('/v1/runs/run-failed/events')) {
    return response({
      events: [
        {
          id: 'event-failed',
          run_id: 'run-failed',
          seq: 1,
          type: 'run.status',
          payload: {
            status: 'failed',
            user_message: '模型服务暂时繁忙，请稍后重试。',
          },
        },
      ],
    });
  }
  if (url.endsWith('/v1/runs/run-retry/events')) {
    return response({
      events: [
        {
          id: 'event-retry',
          run_id: 'run-retry',
          seq: 1,
          type: 'run.retry_created',
          payload: { source_run_id: 'run-failed' },
        },
      ],
    });
  }
  throw new Error(`unexpected request: ${url}`);
}

function RerunHarness() {
  const ledger = usePicoTaskLedger('conversation-failed', false);
  const failedRunId = ledger.run?.status === 'failed' ? ledger.run.id : undefined;
  const activeRunId = ['queued', 'preparing', 'running'].includes(ledger.run?.status || '')
    ? ledger.run?.id
    : undefined;
  return (
    <>
      <TaskRunBar
        isSubmitting={false}
        statusLabel={ledger.statusLabel}
        completedLabel={ledger.run?.status === 'failed' ? ledger.statusLabel : null}
        canCancel={Boolean(activeRunId)}
        canRerun={Boolean(failedRunId)}
        rerunning={ledger.rerunning}
        onRerun={() => void ledger.rerunFailedRun(failedRunId)}
      />
      {ledger.error ? <div role="alert">{ledger.error}</div> : null}
    </>
  );
}

describe('Pico failed run retry integration', () => {
  const originalFetch = global.fetch;

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it('offers a clear retry action and switches to the new queued run', async () => {
    let retried = false;
    let resolveRetry!: (value: Response) => void;
    const retryResponse = new Promise<Response>((resolve) => {
      resolveRetry = resolve;
    });
    const fetchMock = jest.fn((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith('/api/pico/v1/runs/run-failed/retry')) {
        expect(init?.method).toBe('POST');
        return retryResponse;
      }
      return Promise.resolve(ledgerResponse(url, retried));
    });
    global.fetch = fetchMock as typeof fetch;

    render(<RerunHarness />);
    expect(await screen.findByText('失败：模型服务暂时繁忙，请稍后重试。')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '重新运行' }));

    expect(screen.getByRole('button', { name: '重新运行中' })).toBeDisabled();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/pico/v1/runs/run-failed/retry',
      expect.objectContaining({ credentials: 'include', method: 'POST' }),
    );

    retried = true;
    resolveRetry(
      response({
        run: { id: 'run-retry', task_id: 'task-failed', status: 'queued' },
        retried_from_run_id: 'run-failed',
      }),
    );

    expect(await screen.findByRole('status')).toHaveTextContent('等待模型响应');
    expect(screen.queryByText('失败：模型服务暂时繁忙，请稍后重试。')).not.toBeInTheDocument();
  });
});
