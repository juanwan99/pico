import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import {
  getPicoArtifactContent,
  picoAuthedGet,
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  openPicoSandboxBrowser,
  openPicoSandboxDocument,
  type PicoArtifact,
  type PicoRun,
  type PicoRunEvent,
} from '~/data-provider/pico/api';
import ResultPanel, { formatRunTokenUsage } from '../ResultPanel';

jest.mock('~/data-provider/pico/api', () => ({
  getPicoArtifactContent: jest.fn(),
  picoAuthedGet: jest.fn(),
  getPicoSandboxScreenshot: jest.fn(),
  getPicoSandboxSession: jest.fn(),
  postPicoSandboxInput: jest.fn(),
  destroyPicoSandboxSession: jest.fn(),
  openPicoSandboxBrowser: jest.fn(),
  openPicoSandboxDocument: jest.fn(),
  focusPicoSandboxWindow: jest.fn(),
}));
jest.mock('~/utils', () => ({
  cn: (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(' '),
}));

const mockGetPicoArtifactContent = getPicoArtifactContent as jest.MockedFunction<
  typeof getPicoArtifactContent
>;
const mockPicoAuthedGet = picoAuthedGet as jest.MockedFunction<typeof picoAuthedGet>;

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
    mockGetPicoArtifactContent.mockReset();
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
    const pane = await screen.findByTestId('artifact-pane-preview');
    expect(pane).toHaveAttribute('data-kind', 'text');
    expect(screen.getByTestId('artifact-inline-preview')).toHaveTextContent('课程总结内容');
    expect(mockGetPicoArtifactContent).not.toHaveBeenCalled();
    expect(openSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole('button', { name: '关闭预览' }));
    await user.click(screen.getByRole('button', { name: '下载课程总结.md' }));
    await waitFor(() => expect(anchorClickSpy).toHaveBeenCalledTimes(1));
    expect(createObjectURL).toHaveBeenCalledTimes(1);
    expect(mockGetPicoArtifactContent).not.toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:artifact-1');
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
    expect(openSpy).not.toHaveBeenCalled();
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

describe('ResultPanel search sources', () => {
  it('does not park 来源 on top of the sandbox screen', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'search-1',
              run_id: 'run-1',
              seq: 1,
              type: 'search.sources',
              payload: {
                tool: 'web_search',
                honest_miss: false,
                sources: [{ title: 'Gov', url: 'https://www.gov.cn/a' }],
              },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('pico-search-sources')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pico-search-source-link')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-open-files')).not.toBeInTheDocument();
  });

  it('does not show honest-miss 来源 in the right rail either', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'search-miss',
              run_id: 'run-1',
              seq: 1,
              type: 'search.sources',
              payload: { tool: 'web_search', honest_miss: true, sources: [] },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('pico-search-sources-miss')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pico-search-sources')).not.toBeInTheDocument();
  });
});

describe('ResultPanel T-RESULT-OPEN-IN-PANE', () => {
  const mockOpenBrowser = openPicoSandboxBrowser as jest.MockedFunction<
    typeof openPicoSandboxBrowser
  >;

  beforeEach(() => {
    window.localStorage.removeItem('pico.resultPaneWidth');
    mockOpenBrowser.mockReset();
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: jest.fn(() => 'blob:pane'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: jest.fn() });
  });

  it('T1: opening html fills the result pane and does not need window.open', async () => {
    const user = userEvent.setup();
    const openSpy = jest.spyOn(window, 'open');
    renderPanel([
      {
        id: 'art-html',
        title: 'page.html',
        kind: 'html',
        inline: '<html><body><h1>Hello pane</h1></body></html>',
      },
    ]);
    await user.click(screen.getByRole('button', { name: '打开' }));
    const pane = await screen.findByTestId('artifact-pane-preview');
    expect(pane).toHaveAttribute('data-kind', 'html');
    expect(screen.getByTestId('artifact-html-iframe')).toBeInTheDocument();
    expect(openSpy).not.toHaveBeenCalled();
    openSpy.mockRestore();
  });

  it('T2: opening png shows the image in the pane', async () => {
    const user = userEvent.setup();
    mockGetPicoArtifactContent.mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    renderPanel([{ id: 'art-png', title: 'shot.png', kind: 'image' }]);
    await user.click(screen.getByRole('button', { name: '打开' }));
    const pane = await screen.findByTestId('artifact-pane-preview');
    expect(pane).toHaveAttribute('data-kind', 'image');
    expect(screen.getByTestId('artifact-image')).toBeInTheDocument();
  });

  it('T3: opening txt/md shows body text in the pane', async () => {
    const user = userEvent.setup();
    renderPanel([{ id: 'art-txt', title: 'notes.txt', kind: 'text', inline: '正文可见' }]);
    await user.click(screen.getByRole('button', { name: '打开' }));
    const pane = await screen.findByTestId('artifact-pane-preview');
    expect(pane).toHaveAttribute('data-kind', 'text');
    expect(screen.getByTestId('artifact-inline-preview')).toHaveTextContent('正文可见');
  });

  it('T4/F2: opening docx goes to sandbox Writer, not a download or PDF', async () => {
    const user = userEvent.setup();
    const mockOpenDoc = openPicoSandboxDocument as jest.MockedFunction<
      typeof openPicoSandboxDocument
    >;
    mockOpenDoc.mockResolvedValue({
      session_id: 'sbox_bbbbbbbbbbbbbbbbbbbbbbbb',
      url: 'sandbox://writer/报告.docx',
      title: 'LibreOffice Writer · 报告.docx',
      kind: 'writer',
      human_copy: '沙箱已用 LibreOffice 打开这份文档。',
    });
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({
      session_id: 'sbox_bbbbbbbbbbbbbbbbbbbbbbbb',
      title: 'LibreOffice Writer · 报告.docx',
      kind: 'writer',
    });
    mockGetPicoArtifactContent.mockResolvedValue(
      new Blob([new Uint8Array([80, 75, 3, 4])], {
        type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      }),
    );
    renderPanel([{ id: 'art-docx', title: '报告.docx', kind: 'docx' }]);
    await user.click(screen.getByRole('button', { name: '打开' }));
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    expect(mockOpenDoc).toHaveBeenCalled();
    expect(screen.queryByTestId('artifact-office-download')).not.toBeInTheDocument();
  });

  it('T8: opening a PDF attachment previews in-pane and never mistakes it for HTML', async () => {
    const user = userEvent.setup();
    const pdfBytes = new Uint8Array([37, 80, 68, 70]); // %PDF
    mockPicoAuthedGet.mockResolvedValue({
      ok: true,
      blob: async () => new Blob([pdfBytes], { type: 'application/octet-stream' }),
    } as Response);
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '帮我看看这份通知',
              isCreatedByUser: true,
              files: [
                {
                  file_id: 'fid-pdf-1',
                  filename: '培训通知.pdf',
                  filepath: '/uploads/user-1/fid-pdf-1__培训通知.pdf',
                  type: 'application/pdf',
                  size: 4,
                },
              ],
            },
          ]}
        />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId('artifact-open-button'));
    expect(await screen.findByTestId('artifact-pdf-embed')).toBeInTheDocument();
    expect(mockPicoAuthedGet).toHaveBeenCalledWith(
      expect.stringContaining('/api/files/download/user-1/fid-pdf-1'),
    );
    // The old bug: SPA fallback index.html was previewed as「HTML 安全预览」forever.
    expect(screen.queryByText(/安全预览：sandbox 禁用脚本与同源/)).not.toBeInTheDocument();
  });

  it('keeps an uploaded PDF chip when the ledger already has generated HTML', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          picoArtifacts={[{ id: 'art-html', title: '家长会通知.html', kind: 'html', inline: '<p>ok</p>' }]}
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '帮我看看这份通知',
              isCreatedByUser: true,
              files: [
                {
                  file_id: 'fid-pdf-1',
                  filename: '培训通知.pdf',
                  filepath: '/uploads/user-1/fid-pdf-1__培训通知.pdf',
                  type: 'application/pdf',
                  size: 4,
                },
              ],
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(screen.getByText('培训通知.pdf')).toBeInTheDocument();
    expect(screen.getByText('家长会通知.html')).toBeInTheDocument();
  });

  it('does not call a missing PDF「产物服务暂时不可用」', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开',
              isCreatedByUser: true,
              files: [{ file_id: 'orphan', filename: '通知.pdf', type: 'application/pdf' }],
            },
          ]}
        />
      </MemoryRouter>,
    );
    await user.click(screen.getByTestId('artifact-open-button'));
    expect(await screen.findByText(/还没有可打开的内容/)).toBeInTheDocument();
    expect(screen.queryByText(/产物服务暂时不可用/)).not.toBeInTheDocument();
  });

  it('T5: saying 打开 https://example.com opens 网页 via sandbox_browser_open', async () => {
    mockOpenBrowser.mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开 https://example.com',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    await waitFor(() =>
      expect(mockOpenBrowser).toHaveBeenCalledWith('https://example.com/'),
    );
    expect(screen.queryByTitle('browser-preview')).not.toBeInTheDocument();
  });

  it('S1b: 打开浏览器 resolves a default page and opens Chromium', async () => {
    mockOpenBrowser.mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开浏览器',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    await waitFor(() => expect(mockOpenBrowser).toHaveBeenCalledWith('https://example.com/'));
  });

  it('S1c: persisted example.com session still navigates to 腾讯官网', async () => {
    mockOpenBrowser.mockResolvedValue({
      session_id: 'sbox_cccccccccccccccccccccccc',
      url: 'https://www.qq.com/',
      title: '腾讯网',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'sbox-old',
              run_id: 'run-1',
              seq: 1,
              type: 'sandbox.session',
              payload: {
                session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
                url: 'https://example.com/',
                title: 'Example Domain',
              },
            },
          ]}
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开腾讯官网',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockOpenBrowser).toHaveBeenCalledWith('https://www.qq.com/'));
  });

  it('S1b: 打开腾讯官网 resolves qq.com, not silence', async () => {
    mockOpenBrowser.mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://www.qq.com/',
      title: '腾讯网',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开腾讯官网',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    await waitFor(() => expect(mockOpenBrowser).toHaveBeenCalledWith('https://www.qq.com/'));
  });

  it('S2: 打开一份 Word does not invent a classroom file or a webpage', async () => {
    const mockOpenDoc = openPicoSandboxDocument as jest.MockedFunction<
      typeof openPicoSandboxDocument
    >;
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开一份 Word',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('artifact-action-error')).toHaveTextContent(
      '没有可打开的文件',
    );
    expect(screen.queryByTestId('sandbox-web-pane')).not.toBeInTheDocument();
    expect(mockOpenDoc).not.toHaveBeenCalled();
    expect(mockOpenBrowser).not.toHaveBeenCalled();
  });

  it('S3: 你好 does not open a sandbox session', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '你好',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockOpenBrowser).not.toHaveBeenCalled());
    expect(screen.queryByTestId('sandbox-web-pane')).not.toBeInTheDocument();
  });

  it('T6: 来源 is not a right-rail strip even when search ran', async () => {
    mockOpenBrowser.mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'search-1',
              run_id: 'run-1',
              seq: 1,
              type: 'search.sources',
              payload: {
                tool: 'web_search',
                honest_miss: false,
                sources: [{ title: 'Gov', url: 'https://www.gov.cn/a' }],
              },
            },
            {
              id: 'sbox-1',
              run_id: 'run-1',
              seq: 2,
              type: 'sandbox.session',
              payload: {
                session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
                url: 'https://example.com/',
                title: 'Example Domain',
              },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    expect(screen.queryByTestId('pico-search-sources')).not.toBeInTheDocument();
    expect(screen.queryByText('来源')).not.toBeInTheDocument();
  });

  it('R1a: desktop result pane defaults to ≥480 and exposes a drag resizer', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run()} runStatusLabel="已完成" />
      </MemoryRouter>,
    );
    const panel = screen.getByTestId('result-panel');
    expect(Number(panel.getAttribute('data-pane-width'))).toBeGreaterThanOrEqual(480);
    expect(panel.style.getPropertyValue('--pico-result-w')).toBe('480px');
    expect(screen.getByTestId('result-panel-resizer')).toBeInTheDocument();
  });

  it('R1c: fullscreen expands the pane, not just the chrome label', async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run()} runStatusLabel="已完成" />
      </MemoryRouter>,
    );
    const panel = screen.getByTestId('result-panel');
    expect(panel).toHaveAttribute('data-expanded', 'false');
    await user.click(screen.getByTestId('result-panel-chrome-menu'));
    await user.click(screen.getByTestId('result-panel-fullscreen'));
    expect(panel).toHaveAttribute('data-expanded', 'true');
    expect(panel.className).toMatch(/pico-result-panel--expanded/);
    expect(screen.queryByTestId('result-panel-resizer')).not.toBeInTheDocument();
  });

  it('R1b: html preview zoom buttons change the visible ratio', async () => {
    const user = userEvent.setup();
    renderPanel([
      {
        id: 'art-html-zoom',
        title: 'page.html',
        kind: 'html',
        inline: '<html><body><h1>Hello pane</h1></body></html>',
      },
    ]);
    await user.click(screen.getByRole('button', { name: '打开' }));
    expect(await screen.findByTestId('artifact-html-stage')).toHaveAttribute('data-zoom', '100%');
    await user.click(screen.getByTestId('result-panel-chrome-menu'));
    expect(screen.getByTestId('pane-zoom-label')).toHaveTextContent('100%');
    await user.click(screen.getByTestId('pane-zoom-in'));
    expect(screen.getByTestId('pane-zoom-label')).toHaveTextContent('125%');
    expect(screen.getByTestId('artifact-html-stage')).toHaveAttribute('data-zoom', '125%');
    await user.click(screen.getByTestId('pane-zoom-out'));
    expect(screen.getByTestId('pane-zoom-label')).toHaveTextContent('100%');
  });

  it('R1b: webpage screenshot zoom is the same control, not a 390 cap', async () => {
    const user = userEvent.setup();
    mockOpenBrowser.mockResolvedValue({
      sessionId: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          messages={[
            {
              messageId: 'u1',
              conversationId: 'c1',
              parentMessageId: null,
              text: '打开 https://example.com',
              isCreatedByUser: true,
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    await user.click(screen.getByTestId('sandbox-screen-menu'));
    await user.click(screen.getByTestId('pane-zoom-in'));
    expect(screen.getByTestId('pane-zoom-label')).toHaveTextContent('125%');
    expect(screen.getByTestId('sandbox-web-stage')).toHaveAttribute('data-zoom', '125%');
    expect(screen.getByTestId('sandbox-web-viewport').getAttribute('class') || '').not.toMatch(
      /max-w-\[390px\]/,
    );
  });

  it('F3: empty sandbox copy is honest and does not hang a fake webpage', async () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run()} runStatusLabel="已完成" />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('sandbox-empty')).toHaveTextContent('沙箱还没有打开窗口');
    expect(screen.queryByText('还没有隔离网页')).not.toBeInTheDocument();
    expect(screen.queryByTestId('main-delivery-strip')).not.toBeInTheDocument();
    expect(screen.queryByTestId('result-view-menu')).not.toBeInTheDocument();
  });

  it('T7: result chrome has no 概览/文件/沙箱 tab stack and no iframe 浏览器', () => {
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel run={run()} runStatusLabel="已完成" />
      </MemoryRouter>,
    );
    expect(screen.queryByTestId('result-view-menu')).not.toBeInTheDocument();
    expect(screen.queryByTestId('result-view-options')).not.toBeInTheDocument();
    expect(screen.queryByTestId('result-view-browser')).not.toBeInTheDocument();
    expect(screen.queryByText('工作空间文件')).not.toBeInTheDocument();
    expect(screen.getByTestId('sandbox-empty')).toBeInTheDocument();
  });
});

describe('ResultPanel sandbox web pane', () => {
  beforeEach(() => {
    Object.defineProperty(URL, 'createObjectURL', {
      configurable: true,
      value: jest.fn(() => 'blob:sandbox-shot'),
    });
    Object.defineProperty(URL, 'revokeObjectURL', {
      configurable: true,
      value: jest.fn(),
    });
  });

  it('auto-opens 网页 when a sandbox session is on the ledger', async () => {
    const png = new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' });
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(png);
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'sbox-1',
              run_id: 'run-1',
              seq: 1,
              type: 'sandbox.session',
              payload: {
                session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
                url: 'https://example.com/',
                title: 'Example Domain',
                human_copy: '请在此画面自行登录，不要在聊天里发送密码',
              },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-web-pane')).toBeInTheDocument();
    expect(await screen.findByTestId('sandbox-web-viewport')).toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-login-form')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-web-password')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-open-files')).not.toBeInTheDocument();
    expect(screen.queryByText('打开我的文件')).not.toBeInTheDocument();
    expect(screen.queryByText('来源')).not.toBeInTheDocument();
  });

  it('U3: a dead session is honest copy + reopen, not spinner + login', async () => {
    const user = userEvent.setup();
    (getPicoSandboxScreenshot as jest.Mock).mockRejectedValue(new Error('pico 404: gone'));
    (getPicoSandboxSession as jest.Mock).mockRejectedValue(new Error('pico 404: gone'));
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'sbox-1',
              run_id: 'run-1',
              seq: 1,
              type: 'sandbox.session',
              payload: {
                session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
                url: 'https://example.com/',
                title: 'Example Domain',
                human_copy: '请在此画面自行登录，不要在聊天里发送密码',
              },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-dead')).toBeInTheDocument();
    expect(screen.getByTestId('sandbox-dead-copy')).toHaveTextContent('沙箱已关闭');
    expect(screen.getByTestId('sandbox-reopen')).toBeEnabled();
    expect(screen.queryByTestId('sandbox-login-form')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-web-password')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-web-text')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-web-viewport')).not.toBeInTheDocument();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
    expect(screen.queryByText('打开我的文件')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-screen-menu')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('result-panel-chrome-menu'));
    expect(screen.queryByTestId('pane-zoom-in')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sandbox-zoom-menu')).not.toBeInTheDocument();
  });

  it('shows login chrome only when the live page reports input fields', async () => {
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({
      session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://httpbin.org/forms/post',
      title: 'Forms',
      has_text_input: true,
      has_password_input: true,
    });
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ResultPanel
          run={run()}
          runStatusLabel="已完成"
          runEvents={[
            {
              id: 'sbox-1',
              run_id: 'run-1',
              seq: 1,
              type: 'sandbox.session',
              payload: {
                session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
                url: 'https://httpbin.org/forms/post',
                title: 'Forms',
              },
            },
          ]}
        />
      </MemoryRouter>,
    );
    expect(await screen.findByTestId('sandbox-login-form')).toBeInTheDocument();
    expect(screen.getByTestId('sandbox-web-password')).toHaveAttribute('type', 'password');
    expect(screen.getByTestId('sandbox-web-text')).toBeInTheDocument();
  });
});
