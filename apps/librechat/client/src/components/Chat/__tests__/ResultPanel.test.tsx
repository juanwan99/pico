import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import {
  getPicoArtifactContent,
  type PicoArtifact,
  type PicoRun,
  type PicoRunEvent,
} from '~/data-provider/pico/api';
import ResultPanel, { formatRunTokenUsage } from '../ResultPanel';

jest.mock('~/data-provider/pico/api', () => ({
  getPicoArtifactContent: jest.fn(),
}));
jest.mock('~/utils', () => ({
  cn: (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(' '),
}));

const mockGetPicoArtifactContent = getPicoArtifactContent as jest.MockedFunction<
  typeof getPicoArtifactContent
>;

function renderPanel(picoArtifacts: PicoArtifact[]) {
  return render(
    <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <ResultPanel picoArtifacts={picoArtifacts} run={run()} runStatusLabel="已完成" />
    </MemoryRouter>,
  );
}

function run(tokenUsage?: Record<string, unknown>): PicoRun {
  return {
    id: 'run-1',
    task_id: 'task-1',
    status: 'succeeded',
    token_usage: tokenUsage,
  };
}

describe('ResultPanel token usage', () => {
  it('formats total-only and detailed token usage', () => {
    expect(formatRunTokenUsage(run({ total_tokens: 1234 }))).toBe('用量（估算） · 1,234 tokens');
    expect(
      formatRunTokenUsage(run({ input_tokens: 1000, output_tokens: 234, total_tokens: 1234 })),
    ).toBe('用量（估算） · 输入 1,000 · 输出 234 · 共 1,234 tokens');
    expect(
      formatRunTokenUsage(
        run({ prompt_tokens: 10, completion_tokens: 5, total_tokens: 15, estimated: true }),
      ),
    ).toBe('用量（估算） · 输入 10 · 输出 5 · 共 15 tokens');
    expect(formatRunTokenUsage(run({ skill_snapshot: { id: 'analysis' } }))).toBeNull();
  });

  it('shows a concise usage line in the result overview', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run({ total_tokens: 42 })} runStatusLabel="已完成" />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('result-token-usage')).toHaveTextContent('用量（估算） · 42 tokens');
  });

  it('labels estimated token usage for teachers', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run({ total_tokens: 99, estimated: true })}
          runStatusLabel="已完成"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('result-token-usage')).toHaveTextContent('用量（估算） · 99 tokens');
  });

  it('shows the failed user message consistently in the overview and timeline', () => {
    const failedRun = { ...run(), status: 'failed', error: 'technical provider failure' };
    const events: PicoRunEvent[] = [
      {
        id: 'event-failed',
        run_id: failedRun.id,
        seq: 1,
        type: 'run.status',
        payload: {
          status: 'failed',
          user_message: '模型服务暂时繁忙，请稍后重试。',
        },
      },
    ];

    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={failedRun}
          runEvents={events}
          runStatusLabel="失败：模型服务暂时繁忙，请稍后重试。"
        />
      </MemoryRouter>,
    );

    expect(screen.getByTestId('result-status-banner')).toHaveTextContent(
      '失败：模型服务暂时繁忙，请稍后重试。',
    );
    expect(screen.getByText('模型服务暂时繁忙，请稍后重试。')).toBeInTheDocument();
    expect(screen.queryByText(/technical provider failure/)).not.toBeInTheDocument();
  });

  it('exposes result-panel-rerun on the status banner when canRerun', async () => {
    const user = userEvent.setup();
    const onRerun = jest.fn();
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={{ ...run(), status: 'failed' }}
          runStatusLabel="失败：本次回答超出长度上限"
          canRerun
          onRerun={onRerun}
        />
      </MemoryRouter>,
    );

    const btn = screen.getByTestId('result-panel-rerun');
    expect(btn).toBeInTheDocument();
    await user.click(btn);
    expect(onRerun).toHaveBeenCalledTimes(1);
  });
});

describe('ResultPanel artifact actions', () => {
  let openSpy: jest.SpyInstance;
  let anchorClickSpy: jest.SpyInstance;
  let createObjectURL: jest.Mock;
  let revokeObjectURL: jest.Mock;
  let preview: { opener: Window | null; location: { href: string }; close: jest.Mock };

  beforeEach(() => {
    preview = { opener: null, location: { href: '' }, close: jest.fn() };
    openSpy = jest.spyOn(window, 'open').mockReturnValue(preview as unknown as Window);
    anchorClickSpy = jest.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    createObjectURL = jest.fn(() => `blob:artifact-${createObjectURL.mock.calls.length}`);
    revokeObjectURL = jest.fn();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: createObjectURL });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revokeObjectURL });
  });

  afterEach(() => {
    openSpy.mockRestore();
    anchorClickSpy.mockRestore();
  });

  it('opens and downloads inline content without calling the blob API', async () => {
    const user = userEvent.setup();
    renderPanel([
      {
        id: 'artifact-inline',
        title: '课程总结.md',
        kind: 'markdown',
        inline: '课程总结内容',
      },
    ]);

    expect(screen.getByText('课程总结.md')).toBeInTheDocument();
    expect(screen.getByText('markdown · 18B')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '打开' }));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledTimes(1));
    expect(mockGetPicoArtifactContent).not.toHaveBeenCalled();
    expect(preview.location.href).toBe('blob:artifact-1');

    await user.click(screen.getByRole('button', { name: '下载课程总结.md' }));
    await waitFor(() => expect(anchorClickSpy).toHaveBeenCalledTimes(1));
    expect(createObjectURL).toHaveBeenCalledTimes(2);
    expect(mockGetPicoArtifactContent).not.toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:artifact-2');
  });

  it('uses the content API for both open and download when inline content is absent', async () => {
    const user = userEvent.setup();
    mockGetPicoArtifactContent
      .mockResolvedValueOnce(new Blob(['remote preview'], { type: 'text/plain' }))
      .mockResolvedValueOnce(new Blob(['remote download'], { type: 'text/plain' }));
    renderPanel([
      {
        id: 'artifact-blob',
        title: '成绩.csv',
        kind: 'csv',
      },
    ]);

    await user.click(screen.getByRole('button', { name: '打开' }));
    await waitFor(() =>
      expect(mockGetPicoArtifactContent).toHaveBeenNthCalledWith(1, 'artifact-blob', false),
    );

    await user.click(screen.getByRole('button', { name: '下载成绩.csv' }));
    await waitFor(() =>
      expect(mockGetPicoArtifactContent).toHaveBeenNthCalledWith(2, 'artifact-blob', true),
    );
    expect(anchorClickSpy).toHaveBeenCalledTimes(1);
  });

  it('shows honest fallbacks for an empty title and kind', () => {
    renderPanel([
      {
        id: 'artifact-untitled',
        title: '  ',
        kind: '  ',
        inline: '',
      },
    ]);

    expect(screen.getByText('未命名产物')).toBeInTheDocument();
    expect(screen.getByText('类型未知 · 0B')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '下载未命名产物' })).toBeEnabled();
  });

  it('shows a short safe error when opening fails', async () => {
    const user = userEvent.setup();
    mockGetPicoArtifactContent.mockRejectedValue(
      new Error('pico 500: storage password and internal stack trace'),
    );
    renderPanel([
      {
        id: 'artifact-open-failure',
        title: '结果.txt',
        kind: 'text',
      },
    ]);

    await user.click(screen.getByRole('button', { name: '打开' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('打开产物失败，请稍后重试');
    expect(screen.queryByText(/storage password|stack trace/)).not.toBeInTheDocument();
    expect(preview.close).toHaveBeenCalledTimes(1);
  });

  it('shows a permission-safe error when downloading fails', async () => {
    const user = userEvent.setup();
    mockGetPicoArtifactContent.mockRejectedValue(new Error('pico 404: internal object key'));
    renderPanel([
      {
        id: 'artifact-download-failure',
        title: '报告.txt',
        kind: 'text',
      },
    ]);

    await user.click(screen.getByRole('button', { name: '下载报告.txt' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('下载产物失败：产物不存在或无权限');
    expect(screen.queryByText(/internal object key/)).not.toBeInTheDocument();
  });
});
