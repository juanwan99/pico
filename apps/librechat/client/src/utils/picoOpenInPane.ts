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
  '该 Office 文件不支持区内预览或翻页，已开始下载。请用 Word / WPS / LibreOffice 打开。';

export type ArtifactPreviewKind = 'html' | 'image' | 'text' | 'office' | 'download';

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
  if (!candidate) {
    return null;
  }
  // Do not treat "打开 课程总结.md" as a website.
  if (/\.(docx?|pptx?|xlsx?|pdf|md|txt|html?|csv|json|png|jpe?g|gif|webp)$/i.test(candidate)) {
    return null;
  }
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
