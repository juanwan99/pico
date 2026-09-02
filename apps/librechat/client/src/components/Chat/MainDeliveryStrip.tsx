/**
 * #399 R1 — primary-path delivery strip in the main column.
 * Sidebar ResultPanel keeps engineer timeline; humans see open/download first here.
 */
import { useMemo, useState } from 'react';
import { Download, FileText, Loader2 } from 'lucide-react';
import {
  getPicoArtifactContent,
  type PicoArtifact,
  type PicoRunEvent,
} from '~/data-provider/pico/api';
import { artifactsForRun, primaryDeliverables } from '~/utils/picoLatestArtifacts';
import { stashPendingPreviewId } from '~/utils/picoOpenInPane';
import { cn } from '~/utils';
import PicoSearchSources from './PicoSearchSources';
import type { PicoSourceMessage } from '~/utils/picoSearchSources';

const BOOKKEEPING = new Set(['回复摘要', 'summary', 'run summary']);

type Props = {
  artifacts?: PicoArtifact[] | null;
  runId?: string | null;
  runEvents?: PicoRunEvent[] | null;
  messages?: PicoSourceMessage[] | null;
  onOpenResultPanel?: () => void;
};

type Busy = { id: string; type: 'open' | 'download' } | null;

function isBookkeeping(a: PicoArtifact): boolean {
  const title = (a.user_label || a.title || '').trim();
  if (a.kind === 'doc' && title === '回复摘要') {
    return true;
  }
  return BOOKKEEPING.has(title) || BOOKKEEPING.has(title.toLowerCase());
}

function displayName(a: PicoArtifact): string {
  return (a.user_label || a.title || '未命名产物').trim() || '未命名产物';
}

function isHtml(a: PicoArtifact): boolean {
  const name = displayName(a);
  return /\.html?$/i.test(name) || /html/i.test(a.kind || '');
}

function isImage(a: PicoArtifact): boolean {
  const name = displayName(a);
  return /\.(png|jpe?g|gif|webp)$/i.test(name) || /image/i.test(a.kind || '');
}

function isOffice(a: PicoArtifact): boolean {
  const name = displayName(a);
  return /\.(docx?|pptx?|xlsx?|odt|odp|ods)$/i.test(name) || /docx|pptx|xlsx/i.test(a.kind || '');
}

function isPdf(a: PicoArtifact): boolean {
  const name = displayName(a);
  return /\.pdf$/i.test(name) || /pdf/i.test(a.kind || '');
}

function opensInResultPane(a: PicoArtifact): boolean {
  return isOffice(a) || isHtml(a) || isImage(a) || isPdf(a);
}

export default function MainDeliveryStrip({
  artifacts,
  runId,
  runEvents,
  messages,
  onOpenResultPanel,
}: Props) {
  const items = useMemo(
    () =>
      primaryDeliverables(artifactsForRun(artifacts, runId)).filter(
        (a) => a?.id && !isBookkeeping(a),
      ),
    [artifacts, runId],
  );
  const [expanded, setExpanded] = useState(false);
  const [busy, setBusy] = useState<Busy>(null);
  const [error, setError] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string | null>(null);

  const sourcesBlock = <PicoSearchSources events={runEvents} messages={messages} />;

  if (items.length === 0) {
    return (
      <div
        className="mx-auto w-full max-w-[797px] px-2 pb-2 sm:px-0"
        data-testid="main-delivery-strip"
      >
        {sourcesBlock}
      </div>
    );
  }

  const openArtifact = async (a: PicoArtifact) => {
    setBusy({ id: a.id, type: 'open' });
    setError(null);
    setPreviewHtml(null);
    setPreviewImage(null);
    try {
      if (onOpenResultPanel && opensInResultPane(a)) {
        stashPendingPreviewId(a.id);
        onOpenResultPanel();
        return;
      }
      const blob = await getPicoArtifactContent(a.id, false);
      if (isHtml(a) || /text\/html/i.test(blob.type || '')) {
        const text = await blob.text();
        setPreviewTitle(displayName(a));
        setPreviewHtml(text);
        return;
      }
      if (isImage(a) || /image\//i.test(blob.type || '')) {
        const objectUrl = URL.createObjectURL(blob);
        setPreviewTitle(displayName(a));
        setPreviewImage(objectUrl);
        window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120_000);
        return;
      }
      if (isOffice(a)) {
        const htmlBlob = await getPicoArtifactContent(a.id, false, { preview: true });
        const text = await htmlBlob.text();
        if (text.includes('<html') || text.includes('<section') || text.includes('<article')) {
          setPreviewTitle(displayName(a));
          setPreviewHtml(text);
          return;
        }
      }
      // Non-HTML: fall back to download-friendly open
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = displayName(a);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
    } catch (err) {
      setError(err instanceof Error ? err.message : '打开失败');
    } finally {
      setBusy(null);
    }
  };

  const downloadArtifact = async (a: PicoArtifact) => {
    setBusy({ id: a.id, type: 'download' });
    setError(null);
    let objectUrl: string | null = null;
    try {
      const blob = await getPicoArtifactContent(a.id, true);
      objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = displayName(a);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (err) {
      setError(err instanceof Error ? err.message : '下载失败');
    } finally {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      setBusy(null);
    }
  };

  return (
    <div
      className="mx-auto w-full max-w-[797px] px-2 pb-2 sm:px-0"
      data-testid="main-delivery-strip"
    >
      {sourcesBlock}
      <div className="rounded-xl border border-[#cfe0ff] bg-[#f5f9ff] px-3 py-2.5 shadow-[0_1px_2px_rgba(59,111,217,0.08)] dark:border-border-light dark:bg-surface-secondary">
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            className="min-w-0 flex-1 text-left text-[12px] font-semibold text-[#1a3a7a] dark:text-text-primary"
            data-testid="main-delivery-toggle"
            aria-expanded={expanded}
            onClick={() => setExpanded((open) => !open)}
          >
            成品 · {items.length}
            <span className="ml-2 text-[11px] font-medium text-[#3b6fd9]">
              {expanded ? '收起' : '展开'}
            </span>
          </button>
          {onOpenResultPanel ? (
            <button
              type="button"
              className="shrink-0 text-[11px] font-medium text-[#3b6fd9] underline-offset-2 hover:underline"
              onClick={onOpenResultPanel}
              data-testid="main-delivery-open-panel"
            >
              结果区
            </button>
          ) : null}
        </div>
        {expanded ? (
          <>
        <ul className="mt-1.5 space-y-1.5">
          {items.map((a) => {
            const name = displayName(a);
            const opening = busy?.id === a.id && busy.type === 'open';
            const downloading = busy?.id === a.id && busy.type === 'download';
            return (
              <li
                key={a.id}
                className="flex items-center gap-2 rounded-lg border border-black/[0.06] bg-white px-2.5 py-1.5 dark:border-border-light dark:bg-surface-primary"
                data-testid="main-delivery-item"
              >
                <span
                  className={cn(
                    'flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[9px] font-bold',
                    isHtml(a) ? 'bg-[#e8f1ff] text-[#3b6fd9]' : 'bg-[#f0f0f0] text-[#6b6b6b]',
                  )}
                  aria-hidden
                >
                  {isHtml(a) ? 'HTML' : <FileText className="h-3.5 w-3.5" />}
                </span>
                <p className="min-w-0 flex-1 truncate text-[13px] font-medium" title={name}>
                  {name}
                </p>
                <button
                  type="button"
                  data-testid="main-delivery-open"
                  className="h-8 rounded-md border border-black/[0.08] px-2.5 text-[12px] font-medium disabled:opacity-50"
                  disabled={busy !== null}
                  onClick={() => void openArtifact(a)}
                >
                  {opening ? '打开中' : '打开'}
                </button>
                <button
                  type="button"
                  data-testid="main-delivery-download"
                  className="inline-flex h-8 items-center gap-1 rounded-md bg-[#1a1a1a] px-2.5 text-[12px] font-semibold text-white disabled:opacity-50 dark:bg-white dark:text-[#1a1a1a]"
                  disabled={busy !== null}
                  onClick={() => void downloadArtifact(a)}
                  aria-label={`下载${name}`}
                >
                  {downloading ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Download className="h-3.5 w-3.5" />
                  )}
                  下载
                </button>
              </li>
            );
          })}
        </ul>
        {previewHtml !== null ? (
          <div
            className="mt-2 overflow-hidden rounded-lg border border-black/[0.08] bg-[#ececec] dark:border-border-light"
            data-testid="main-delivery-html-preview"
          >
            <div className="flex items-center justify-between gap-2 bg-white px-2 py-1">
              <p className="truncate text-[12px] font-medium">{previewTitle}</p>
              <button
                type="button"
                className="text-[11px] text-[#6b6b6b] underline"
                onClick={() => {
                  setPreviewHtml(null);
                  setPreviewTitle(null);
                }}
              >
                关闭预览
              </button>
            </div>
            <iframe
              title={previewTitle || 'HTML 预览'}
              sandbox={/\.(docx?|pptx?|xlsx?)$/i.test(previewTitle || '') ? '' : 'allow-scripts'}
              referrerPolicy="no-referrer"
              srcDoc={previewHtml}
              className="h-[28rem] w-full border-0 bg-white"
              data-testid="main-delivery-html-iframe"
            />
          </div>
        ) : null}
        {previewImage !== null ? (
          <div
            className="mt-2 overflow-hidden rounded-lg border border-black/[0.08] bg-[#ececec] dark:border-border-light"
            data-testid="main-delivery-image-preview"
          >
            <div className="flex items-center justify-between gap-2 bg-white px-2 py-1">
              <p className="truncate text-[12px] font-medium">{previewTitle}</p>
              <button
                type="button"
                className="text-[11px] text-[#6b6b6b] underline"
                onClick={() => {
                  setPreviewImage(null);
                  setPreviewTitle(null);
                }}
              >
                关闭预览
              </button>
            </div>
            <img
              src={previewImage}
              alt={previewTitle || '图片预览'}
              className="mx-auto max-h-[28rem] w-auto max-w-full object-contain"
              data-testid="main-delivery-image"
            />
          </div>
        ) : null}
        {error ? (
          <p className="mt-1.5 text-[11px] text-red-700" role="alert">
            {error}
          </p>
        ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}
