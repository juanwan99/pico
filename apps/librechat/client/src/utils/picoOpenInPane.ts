/**
 * T-RESULT-OPEN-IN-PANE: one path for file preview + public-site open.
 * iframe「浏览器」is not the open-website entry.
 */

/** Public chrome is sandbox-only. overview/files stay as internal preview states. */
export const RESULT_PANE_VIEWS = ['web'] as const;
export type ResultPaneView = 'overview' | 'files' | 'web';

export const RESULT_PANE_VIEW_LABEL: Record<ResultPaneView, string> = {
  overview: '概览',
  files: '工作空间文件',
  web: '沙箱',
};

export const OFFICE_NO_PREVIEW_COPY =
  '打不开这份文档的内容页。请点下载，用 Word / WPS / LibreOffice 打开。';

export type ArtifactPreviewKind = 'html' | 'image' | 'text' | 'office' | 'pdf' | 'download';

export function isOfficeFilename(name: string, kindLabel = ''): boolean {
  const value = `${name} ${kindLabel}`.toLowerCase();
  return /\.(docx|pptx|xlsx)(?:\s|$)/i.test(value) || /\b(docx|pptx|xlsx)\b/.test(value);
}

export function classifyArtifactPreview(
  name: string,
  kindLabel = '',
  blobType = '',
): ArtifactPreviewKind {
  const value = `${name} ${kindLabel}`.toLowerCase();
  if (isOfficeFilename(name, kindLabel)) {
    return 'office';
  }
  if (/\.pdf(?:\s|$)/i.test(value) || /\bpdf\b/i.test(kindLabel) || /application\/pdf/i.test(blobType)) {
    return 'pdf';
  }
  if (/(?:\.html?|html)/.test(value) || /text\/html/i.test(blobType)) {
    return 'html';
  }
  if (/\.(png|jpe?g|gif|webp)$/i.test(name) || /image/i.test(kindLabel) || /image\//i.test(blobType)) {
    return 'image';
  }
  if (
    /(?:\.txt|\.md|\.json|\.csv|\.log|text|markdown|plain|json)/.test(value) ||
    /text|json|markdown|plain|csv/i.test(blobType)
  ) {
    return 'text';
  }
  return 'download';
}

/**
 * Message attachments store `/uploads/{userId}/{file_id}__{name}` which has no
 * serving route (SPA fallback would answer index.html). Real bytes live behind
 * the owner-checked download API.
 */
export function picoUploadDownloadUrl(
  filepath: string,
  fileId?: string,
  ownerUserId?: string,
): string {
  if (filepath && !/^\/uploads\//i.test(filepath)) {
    return filepath;
  }
  const userId = /^\/uploads\/([^/]+)\//i.exec(filepath || '')?.[1] || ownerUserId?.trim() || '';
  const id = fileId?.trim() || '';
  return userId && id ? `/api/files/download/${userId}/${id}` : filepath;
}

/** Honest open/download copy. Do not treat a missing file as「产物服务暂时不可用」. */
export function humanArtifactActionError(
  action: 'open' | 'download' | 'keep',
  error: unknown,
): string {
  const verb = action === 'open' ? '打开' : action === 'keep' ? '保留' : '下载';
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('401')) {
    return `${verb}产物失败：登录已失效，请刷新页面后重新登录。`;
  }
  if (/\b403\b/.test(message) || /\b404\b/.test(message)) {
    return `${verb}产物失败：产物不存在或无权限。`;
  }
  if (/\bpico_upstream_unavailable\b/.test(message) || /\bECONNREFUSED\b/.test(message)) {
    return `${verb}产物失败：产物服务暂时连不上，请稍后重试。`;
  }
  if (/artifact content unavailable/i.test(message)) {
    return `${verb}产物失败：这份还没有可打开的内容。上传的 PDF 请点结果区该文件的「打开」；生成件从结果区下载。`;
  }
  if (/\b502\b/.test(message)) {
    return `${verb}产物失败：网关返回 502，请稍后重试；若一直这样，请让管理员看产物服务日志。`;
  }
  return `${verb}产物失败，请稍后重试。`;
}

const BROWSER_DEFAULT_URL = 'https://example.com/';
const SITE_ALIASES: Array<{ test: RegExp; url: string }> = [
  { test: /腾讯官网|腾讯网/i, url: 'https://www.qq.com/' },
];

function looksLikeOfficeOpen(text: string): boolean {
  return /(?:打开|open).{0,16}(?:word|Word|WORD|docx|doc\b|文档|字处理|表格|excel|xlsx|ppt|pptx|幻灯|演示)/i.test(
    text,
  );
}

function canonicalizeHttpUrl(candidate: string): string | null {
  const href = /^https?:\/\//i.test(candidate) ? candidate : `https://${candidate}`;
  try {
    const parsed = new URL(href);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
      return null;
    }
    if (!parsed.hostname.includes('.')) {
      return null;
    }
    return parsed.toString();
  } catch {
    return null;
  }
}

/** Public URL the teacher asked to open in the right-hand 网页 pane. */
export function detectOpenWebsiteIntent(text: string): string | null {
  const raw = (text || '').trim();
  if (!raw) {
    return null;
  }
  const bare = raw.match(/^(https?:\/\/[^\s]+)$/i);
  const spoken = raw.match(
    /(?:打开|open)\s+(?:一下|下)?\s*(https?:\/\/[^\s]+|(?:www\.)?[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+[^\s]*)/i,
  );
  const candidate = (bare?.[1] || spoken?.[1] || '').replace(/[.,;:!?）)]+$/, '');
  if (candidate) {
    // Do not treat "打开 课程总结.md" as a website.
    if (/\.(docx?|pptx?|xlsx?|pdf|md|txt|html?|csv|json|png|jpe?g|gif|webp)$/i.test(candidate)) {
      return null;
    }
    return canonicalizeHttpUrl(candidate);
  }
  // Word/Excel stay on the Writer path — never alias them to a webpage.
  if (looksLikeOfficeOpen(raw) && !/(?:https?:\/\/|www\.)/i.test(raw)) {
    return null;
  }
  if (
    /(?:打开|open).{0,10}(?:浏览器|chrome\b|chromium\b|browser\b)/i.test(raw) ||
    /^(?:打开|open)\s*(?:一下|下)?\s*(?:网站|网页)$/i.test(raw)
  ) {
    return BROWSER_DEFAULT_URL;
  }
  for (const alias of SITE_ALIASES) {
    if (/(?:打开|open)/i.test(raw) && alias.test.test(raw)) {
      return alias.url;
    }
  }
  return null;
}

export type OfficeOpenIntent = {
  kind: 'writer' | 'calc' | 'impress';
  filename?: string;
};

export function detectOpenOfficeIntent(text: string): OfficeOpenIntent | null {
  const raw = (text || '').trim();
  if (!raw) {
    return null;
  }
  if (detectOpenWebsiteIntent(raw)) {
    return null;
  }
  const named = raw.match(
    /(?:打开|open)\s+(?:一下|下)?\s*([^\s]+\.(?:docx?|xlsx?|pptx?|odt|ods|odp))\b/i,
  );
  if (named?.[1]) {
    const filename = named[1];
    const kind: OfficeOpenIntent['kind'] = /\.(xlsx?|ods|csv)$/i.test(filename)
      ? 'calc'
      : /\.(pptx?|odp)$/i.test(filename)
        ? 'impress'
        : 'writer';
    return { kind, filename };
  }
  if (/(?:打开|open).{0,12}(?:表格|excel|xlsx|spreadsheet)/i.test(raw)) {
    return { kind: 'calc' };
  }
  if (/(?:打开|open).{0,12}(?:ppt|pptx|幻灯|演示)/i.test(raw)) {
    return { kind: 'impress' };
  }
  if (/(?:打开|open).{0,16}(?:word|Word|WORD|docx|doc\b|文档|字处理)/i.test(raw)) {
    return { kind: 'writer' };
  }
  return null;
}

export function latestUserOpenOfficeIntent(
  messages:
    | Array<{ text?: unknown; isCreatedByUser?: boolean } | null | undefined>
    | null
    | undefined,
): OfficeOpenIntent | null {
  if (!messages?.length) {
    return null;
  }
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (!message?.isCreatedByUser) {
      continue;
    }
    return detectOpenOfficeIntent(String(message.text || ''));
  }
  return null;
}

export function latestUserOpenWebsiteIntent(
  messages:
    | Array<{ text?: unknown; isCreatedByUser?: boolean } | null | undefined>
    | null
    | undefined,
): string | null {
  if (!messages?.length) {
    return null;
  }
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (!message?.isCreatedByUser) {
      continue;
    }
    return detectOpenWebsiteIntent(String(message.text || ''));
  }
  return null;
}

export async function readBlobText(blob: Blob, inline?: string): Promise<string> {
  if (typeof inline === 'string') {
    return inline;
  }
  if (blob && typeof blob.text === 'function') {
    return blob.text();
  }
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error || new Error('read failed'));
    reader.readAsText(blob);
  });
}

/** Desktop default; CSS --pico-wb-result-w must match or !important wins. */
export const RESULT_PANE_DEFAULT_WIDTH = 480;
/** Drag floor — not smaller than the pre-R1 Tailwind widths (340/390). */
export const RESULT_PANE_MIN_WIDTH = 340;
export const RESULT_PANE_MAX_WIDTH = 880;
export const RESULT_PANE_NARROW_BREAKPOINT = 640;
export const RESULT_PANE_WIDTH_STORAGE_KEY = 'pico.resultPaneWidth';
export const RESULT_PANE_ZOOM_MIN = 0.5;
export const RESULT_PANE_ZOOM_MAX = 2;
export const RESULT_PANE_ZOOM_STEP = 0.25;

export function clampResultPaneWidth(width: number, viewportWidth = 1280): number {
  const numeric = Number.isFinite(width) ? width : RESULT_PANE_DEFAULT_WIDTH;
  const vp = Number.isFinite(viewportWidth) && viewportWidth > 0 ? viewportWidth : 1280;
  const narrow = vp <= RESULT_PANE_NARROW_BREAKPOINT;
  const max = narrow
    ? vp
    : Math.min(RESULT_PANE_MAX_WIDTH, Math.max(RESULT_PANE_MIN_WIDTH, vp - 280));
  const min = narrow ? Math.min(RESULT_PANE_MIN_WIDTH, vp) : RESULT_PANE_MIN_WIDTH;
  return Math.round(Math.min(max, Math.max(min, numeric)));
}

export function readStoredResultPaneWidth(
  storage?: Pick<Storage, 'getItem'> | null,
  viewportWidth = 1280,
): number {
  try {
    const raw = storage?.getItem(RESULT_PANE_WIDTH_STORAGE_KEY);
    const parsed = raw == null || raw === '' ? NaN : Number(raw);
    return clampResultPaneWidth(
      Number.isFinite(parsed) ? parsed : RESULT_PANE_DEFAULT_WIDTH,
      viewportWidth,
    );
  } catch {
    return clampResultPaneWidth(RESULT_PANE_DEFAULT_WIDTH, viewportWidth);
  }
}

export function clampResultPaneZoom(zoom: number): number {
  const numeric = Number.isFinite(zoom) ? zoom : 1;
  const stepped = Math.round(numeric / RESULT_PANE_ZOOM_STEP) * RESULT_PANE_ZOOM_STEP;
  return Math.min(RESULT_PANE_ZOOM_MAX, Math.max(RESULT_PANE_ZOOM_MIN, Number(stepped.toFixed(2))));
}

export function formatResultPaneZoom(zoom: number): string {
  return `${Math.round(clampResultPaneZoom(zoom) * 100)}%`;
}
