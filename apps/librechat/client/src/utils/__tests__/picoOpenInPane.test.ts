import {
  classifyArtifactPreview,
  detectOpenWebsiteIntent,
  latestUserOpenWebsiteIntent,
  RESULT_PANE_VIEWS,
  RESULT_PANE_VIEW_LABEL,
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
