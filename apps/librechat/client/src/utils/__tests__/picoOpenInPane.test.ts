import {
  classifyArtifactPreview,
  clampResultPaneWidth,
  clampResultPaneZoom,
  detectOpenWebsiteIntent,
  formatResultPaneZoom,
  latestUserOpenWebsiteIntent,
  readStoredResultPaneWidth,
  RESULT_PANE_DEFAULT_WIDTH,
  RESULT_PANE_MIN_WIDTH,
  RESULT_PANE_VIEWS,
  RESULT_PANE_VIEW_LABEL,
  RESULT_PANE_WIDTH_STORAGE_KEY,
} from '../picoOpenInPane';

describe('picoOpenInPane', () => {
  it('T1/T9: html/image/text classify as in-pane preview; office is honest download', () => {
    expect(classifyArtifactPreview('page.html', 'html')).toBe('html');
    expect(classifyArtifactPreview('shot.png', 'image')).toBe('image');
    expect(classifyArtifactPreview('课程总结.md', 'markdown')).toBe('text');
    expect(classifyArtifactPreview('notes.txt', 'text')).toBe('text');
    expect(classifyArtifactPreview('报告.docx', 'docx')).toBe('office');
    expect(RESULT_PANE_VIEWS).toEqual(['overview', 'files', 'web']);
    expect(RESULT_PANE_VIEW_LABEL.web).toBe('网页');
    expect(RESULT_PANE_VIEW_LABEL).not.toHaveProperty('browser');
  });

  it('T5/T9: 打开 example.com is a website intent; 打开 file.md is not', () => {
    expect(detectOpenWebsiteIntent('打开 https://example.com')).toBe('https://example.com/');
    expect(detectOpenWebsiteIntent('打开 example.com')).toBe('https://example.com/');
    expect(detectOpenWebsiteIntent('open https://example.com/')).toBe('https://example.com/');
    expect(detectOpenWebsiteIntent('https://example.com')).toBe('https://example.com/');
    expect(detectOpenWebsiteIntent('打开 课程总结.md')).toBeNull();
    expect(detectOpenWebsiteIntent('打开 报告.docx')).toBeNull();
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
