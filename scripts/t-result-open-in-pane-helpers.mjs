#!/usr/bin/env bun
/** Run T1/T5 helper locks without the full LibreChat Jest graph. */
import {
  classifyArtifactPreview,
  detectOpenWebsiteIntent,
  latestUserOpenWebsiteIntent,
  RESULT_PANE_VIEWS,
  RESULT_PANE_VIEW_LABEL,
} from '../apps/librechat/client/src/utils/picoOpenInPane.ts';

const m = {
  classifyArtifactPreview,
  detectOpenWebsiteIntent,
  latestUserOpenWebsiteIntent,
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
assert(JSON.stringify(m.RESULT_PANE_VIEWS) === JSON.stringify(['overview', 'files', 'web']), 'T7 views');
assert(!('browser' in m.RESULT_PANE_VIEW_LABEL), 'T7 no iframe menu');
assert(m.detectOpenWebsiteIntent('打开 https://example.com') === 'https://example.com/', 'T5 url');
assert(m.detectOpenWebsiteIntent('打开 example.com') === 'https://example.com/', 'T5 host');
assert(m.detectOpenWebsiteIntent('打开 课程总结.md') === null, 'T5 not file');
assert(
  m.latestUserOpenWebsiteIntent([
    { isCreatedByUser: true, text: '打开 https://example.com' },
    { isCreatedByUser: false, text: '好的' },
  ]) === 'https://example.com/',
  'T5 latest user',
);

console.log('t-result-open-in-pane-helpers: T1 T2 T3 T4 T5 T7 OK');
