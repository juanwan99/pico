#!/usr/bin/env bun
/** Run T1/T5 helper locks without the full LibreChat Jest graph. */
import {
  classifyArtifactPreview,
  clampResultPaneWidth,
  clampResultPaneZoom,
  detectOpenWebsiteIntent,
  formatResultPaneZoom,
  latestUserOpenWebsiteIntent,
  RESULT_PANE_DEFAULT_WIDTH,
  RESULT_PANE_MIN_WIDTH,
  RESULT_PANE_VIEWS,
  detectOpenOfficeIntent,
  RESULT_PANE_VIEW_LABEL,
} from '../apps/librechat/client/src/utils/picoOpenInPane.ts';

const m = {
  classifyArtifactPreview,
  clampResultPaneWidth,
  clampResultPaneZoom,
  detectOpenOfficeIntent,
  detectOpenWebsiteIntent,
  formatResultPaneZoom,
  latestUserOpenWebsiteIntent,
  RESULT_PANE_DEFAULT_WIDTH,
  RESULT_PANE_MIN_WIDTH,
  RESULT_PANE_VIEWS,
  RESULT_PANE_VIEW_LABEL,
};

function assert(cond, msg) {
  if (!cond) {
    throw new Error(msg);
  }
}

assert(m.classifyArtifactPreview('page.html', 'html') === 'html', 'T1 html');
assert(m.classifyArtifactPreview('shot.png', 'image') === 'image', 'T2 image');
assert(m.classifyArtifactPreview('课程总结.md', 'markdown') === 'text', 'T3 text');
assert(m.classifyArtifactPreview('报告.docx', 'docx') === 'office', 'T4 office');
assert(JSON.stringify(m.RESULT_PANE_VIEWS) === JSON.stringify(['web']), 'T7 views sandbox-only');
assert(m.RESULT_PANE_VIEW_LABEL.web === '沙箱', 'sandbox label');
assert(!('browser' in m.RESULT_PANE_VIEW_LABEL), 'T7 no iframe menu');
assert(m.detectOpenOfficeIntent('打开一个 word 文档在沙箱')?.kind === 'writer', 'F2 word');
assert(m.detectOpenOfficeIntent('打开 https://example.com') === null, 'F2 not url');
assert(m.detectOpenWebsiteIntent('打开 https://example.com') === 'https://example.com/', 'T5 url');
assert(m.detectOpenWebsiteIntent('打开 example.com') === 'https://example.com/', 'T5 host');
assert(m.detectOpenWebsiteIntent('打开 课程总结.md') === null, 'T5 not file');
assert(m.detectOpenWebsiteIntent('打开浏览器') === 'https://example.com/', 'S1b browser');
assert(m.detectOpenWebsiteIntent('打开腾讯官网') === 'https://www.qq.com/', 'S1b tencent');
assert(m.detectOpenWebsiteIntent('打开一份 Word') === null, 'S1b not word');
assert(m.detectOpenWebsiteIntent('你好') === null, 'S3 idle');
assert(
  m.latestUserOpenWebsiteIntent([
    { isCreatedByUser: true, text: '打开 https://example.com' },
    { isCreatedByUser: false, text: '好的' },
  ]) === 'https://example.com/',
  'T5 latest user',
);

assert(m.RESULT_PANE_DEFAULT_WIDTH >= 480, 'R1a default');
assert(m.RESULT_PANE_MIN_WIDTH >= 340, 'R1a min');
assert(m.clampResultPaneWidth(480, 1280) === 480, 'R1a 480 desktop');
assert(m.clampResultPaneWidth(480, 390) === 390, 'R1d 390 clamp');
assert(m.formatResultPaneZoom(1.25) === '125%', 'R1b label');
assert(m.clampResultPaneZoom(9) === 2, 'R1b max');

console.log('t-result-open-in-pane-helpers: T1 T2 T3 T4 T5 T7 R1a R1b R1d OK');
