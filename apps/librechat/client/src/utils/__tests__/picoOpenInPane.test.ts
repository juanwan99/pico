import {
  classifyArtifactPreview,
  stashPendingPreviewId,
  peekPendingPreviewId,
  takePendingPreviewId,
  clampResultPaneWidth,
  clampResultPaneZoom,
  detectOpenOfficeIntent,
  detectOpenWebsiteIntent,
  formatResultPaneZoom,
  latestUserOpenWebsiteIntent,
  humanArtifactActionError,
  picoUploadDownloadUrl,
  readStoredResultPaneWidth,
  RESULT_PANE_DEFAULT_WIDTH,
  RESULT_PANE_MIN_WIDTH,
  RESULT_PANE_VIEWS,
  RESULT_PANE_VIEW_LABEL,
  RESULT_PANE_WIDTH_STORAGE_KEY,
} from '../picoOpenInPane';

describe('picoOpenInPane', () => {
  it('stashes a pending preview id and notifies the result panel', () => {
    const seen: string[] = [];
    const onPending = (event: Event) => {
      seen.push(String((event as CustomEvent<string>).detail || ''));
    };
    window.addEventListener('pico:pending-preview', onPending);
    sessionStorage.clear();
    stashPendingPreviewId('art-office-1');
    expect(peekPendingPreviewId()).toBe('art-office-1');
    expect(seen).toEqual(['art-office-1']);
    expect(takePendingPreviewId()).toBe('art-office-1');
    expect(peekPendingPreviewId()).toBeNull();
    window.removeEventListener('pico:pending-preview', onPending);
  });

  it('T1/T9: html/image/text classify as in-pane preview; office is content-box', () => {
    expect(classifyArtifactPreview('page.html', 'html')).toBe('html');
    expect(classifyArtifactPreview('shot.png', 'image')).toBe('image');
    expect(classifyArtifactPreview('课程总结.md', 'markdown')).toBe('text');
    expect(classifyArtifactPreview('notes.txt', 'text')).toBe('text');
    expect(classifyArtifactPreview('报告.docx', 'docx')).toBe('office');
    expect(classifyArtifactPreview('通知.pdf', 'application/pdf')).toBe('pdf');
    expect(classifyArtifactPreview('通知.pdf', '', 'application/pdf')).toBe('pdf');
    expect(classifyArtifactPreview('通知.pdf', '', 'application/octet-stream')).toBe('pdf');
    expect(picoUploadDownloadUrl('/uploads/u1/fid__通知.pdf', 'fid')).toBe(
      '/api/files/download/u1/fid',
    );
    expect(picoUploadDownloadUrl('/uploads/u1/fid__通知.pdf')).toBe(
      '/uploads/u1/fid__通知.pdf',
    );
    expect(picoUploadDownloadUrl('', 'fid', 'u1')).toBe('/api/files/download/u1/fid');
    expect(picoUploadDownloadUrl('https://example.com/a.pdf', 'fid')).toBe(
      'https://example.com/a.pdf',
    );
    expect(humanArtifactActionError('open', new Error('artifact content unavailable'))).toMatch(
      /打开产物失败：这份还没有可打开的内容/,
    );
    expect(humanArtifactActionError('open', new Error('pico 502: artifact preview'))).not.toMatch(
      /产物服务暂时不可用/,
    );
    expect(
      humanArtifactActionError('open', new Error('pico 502: pico_upstream_unavailable')),
    ).toMatch(/产物服务暂时连不上/);
    expect(RESULT_PANE_VIEWS).toEqual(['web']);
    expect(RESULT_PANE_VIEW_LABEL.web).toBe('沙箱');
    expect(RESULT_PANE_VIEW_LABEL).not.toHaveProperty('browser');
  });

  it('F2: 打开 word/docx is office intent, not a website', () => {
    expect(detectOpenOfficeIntent('打开一个 word 文档在沙箱')).toEqual({ kind: 'writer' });
    expect(detectOpenOfficeIntent('打开一个测试word')).toEqual({ kind: 'writer' });
    expect(detectOpenOfficeIntent('打开 课堂笔记.docx')).toEqual({
      kind: 'writer',
      filename: '课堂笔记.docx',
    });
    expect(detectOpenOfficeIntent('打开 https://example.com')).toBeNull();
  });

  it('does not invent a classroom filename when none was named', () => {
    expect(detectOpenOfficeIntent('打开一份 Word')?.filename).toBeUndefined();
    expect(detectOpenOfficeIntent('打开一个 word 文档在沙箱')?.filename).toBeUndefined();
  });

  it.each([
    ['https://example.com/a', 'https://example.com/a'],
    ['打开 https://example.com', 'https://example.com/'],
    ['打开 https://no-such-host.invalid', 'https://no-such-host.invalid/'],
    ['打开一下 example.com', 'https://example.com/'],
    ['open www.example.com', 'https://www.example.com/'],
    ['open https://example.com/', 'https://example.com/'],
    ['  打开https://example.com。  ', 'https://example.com/'],
    ['https://example.com/path!）', 'https://example.com/path'],
    ['打开 https://example.com/guide.pdf.', 'https://example.com/guide.pdf'],
    [
      '打开 https://example.com/search?q=a%20b&sort=1#top！',
      'https://example.com/search?q=a%20b&sort=1#top',
    ],
    ['打开浏览器', 'https://example.com/'],
    ['打开一下浏览器', 'https://example.com/'],
    ['打开网页！', 'https://example.com/'],
    ['打开网站!', 'https://example.com/'],
    ['打开腾讯网。', 'https://www.qq.com/'],
    ['打开腾讯官网', 'https://www.qq.com/'],
  ])('opens the website shortcut %s', (message, url) => {
    expect(detectOpenWebsiteIntent(message)).toBe(url);
  });

  it.each([
    '打开 https://example.com。未登录就停在登录页',
    '请帮我打开 https://example.com 看看首页',
    '先阅读要求\n打开 https://example.com\n未登录就停在登录页',
    '打开 example.com 然后截图',
    'openai.example.com',
    '先登录。再打开 https://example.com中文说明',
    '打开 example.com。看完告诉我',
    '打开 https://example.com/index.html。查看首页',
    '打开 https://example.com/guide.pdf，查看手册',
    '打开 https://example.com/search?q=a%20b&sort=1#top，看看结果',
    '打开浏览器，再看首页',
    '打开网页 然后截图',
    '请打开腾讯网',
    '打开腾讯网看看首页',
    '打开 课程总结.md',
    '打开 报告.docx',
    '打开 index.html',
    '你好',
    '打开一份 Word',
  ])('skips the website shortcut for %s', (message) => {
    expect(detectOpenWebsiteIntent(message)).toBeNull();
  });

  it.each([
    '打开 https://example.com。再打开报告.docx',
    '打开 www.example.com 的表格',
    '先读 http://example.com 的说明，再打开 Word',
  ])('skips the office shortcut for a message with a URL: %s', (message) => {
    expect(detectOpenWebsiteIntent(message)).toBeNull();
    expect(detectOpenOfficeIntent(message)).toBeNull();
  });

  it('R1a/R1d: default 480, drag floor 340, 390 viewport cannot overflow', () => {
    expect(RESULT_PANE_DEFAULT_WIDTH).toBeGreaterThanOrEqual(480);
    expect(RESULT_PANE_MIN_WIDTH).toBeGreaterThanOrEqual(340);
    expect(clampResultPaneWidth(480, 1280)).toBe(480);
    expect(clampResultPaneWidth(200, 1280)).toBe(340);
    expect(clampResultPaneWidth(480, 390)).toBe(390);
    expect(clampResultPaneWidth(900, 390)).toBe(390);
  });

  it('R1b: zoom clamps to 50–200% and formats a visible ratio', () => {
    expect(formatResultPaneZoom(1)).toBe('100%');
    expect(formatResultPaneZoom(1.25)).toBe('125%');
    expect(clampResultPaneZoom(0.1)).toBe(0.5);
    expect(clampResultPaneZoom(4)).toBe(2);
  });

  it('reads a stored pane width and ignores junk', () => {
    expect(
      readStoredResultPaneWidth(
        { getItem: (key) => (key === RESULT_PANE_WIDTH_STORAGE_KEY ? '520' : null) },
        1280,
      ),
    ).toBe(520);
    expect(readStoredResultPaneWidth({ getItem: () => 'nope' }, 1280)).toBe(480);
  });

  it('reads the latest user turn only', () => {
    expect(
      latestUserOpenWebsiteIntent([
        { isCreatedByUser: true, text: '打开 https://example.com' },
        { isCreatedByUser: false, text: '好的' },
      ]),
    ).toBe('https://example.com/');
    expect(
      latestUserOpenWebsiteIntent([
        { isCreatedByUser: true, text: '打开 https://example.com' },
        { isCreatedByUser: true, text: '改成打开 课程总结.md' },
      ]),
    ).toBeNull();
  });
});
