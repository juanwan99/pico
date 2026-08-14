/**
 * T-RESULT-OPEN-IN-PANE: one path for file preview + public-site open.
 * iframe「浏览器」is not the open-website entry.
 */

export const RESULT_PANE_VIEWS = ['overview', 'files', 'web'] as const;
export type ResultPaneView = (typeof RESULT_PANE_VIEWS)[number];

export const RESULT_PANE_VIEW_LABEL: Record<ResultPaneView, string> = {
  overview: '概览',
  files: '工作空间文件',
  web: '网页',
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
