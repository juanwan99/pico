/**
 * Task result panel — right-hand sandbox screen.
 * No 概览/文件/沙箱 tab stack. Files open as the sandbox folder.
 * Chat column carries MainDeliveryStrip (open/download first); this panel
 * keeps the engineer timeline + full chips.
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { PicoIcon } from '~/components/ui/pico-icons';
import type { TMessage } from 'librechat-data-provider';
import {
  getPicoArtifactContent,
  picoAuthedGet,
  openPicoSandboxBrowser,
  openPicoSandboxDocument,
  type PicoArtifact,
  type PicoRun,
  type PicoRunEvent,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';
import {
  classifyArtifactPreview,
  clampResultPaneWidth,
  humanArtifactActionError,
  latestUserOpenOfficeIntent,
  latestUserOpenWebsiteIntent,
  picoUploadDownloadUrl,
  readBlobText,
  readStoredResultPaneWidth,
  RESULT_PANE_WIDTH_STORAGE_KEY,
  type OfficeOpenIntent,
  type ResultPaneView,
} from '~/utils/picoOpenInPane';
import { latestArtifactsByFilename } from '~/utils/picoLatestArtifacts';
import { collectPicoSandboxSession } from '~/utils/picoSandboxSession';
import RunLoadingIndicator from './RunLoadingIndicator';
import RunTimeline from './RunTimeline';
import SandboxWebPane from './SandboxWebPane';
import PaneZoomBar, { usePaneZoom } from './PaneZoomBar';

type TopView = ResultPaneView;

type ArtifactItem = {
  id: string;
  name: string;
  kindLabel: string;
  sizeLabel: string;
  kind: 'txt' | 'file' | 'html' | 'other';
  url?: string;
  body?: string;
  picoArtifact?: boolean;
  contentEncoding?: string;
  byteSize?: number;
  contentSha256?: string;
};

type ArtifactAction = {
  id: string;
  type: 'open' | 'download';
};

const UNNAMED_ARTIFACT = '未命名产物';
const UNNAMED_ATTACHMENT = '未命名附件';
const UNKNOWN_KIND = '类型未知';

function artifactActionError(action: ArtifactAction['type'], error: unknown): string {
  return humanArtifactActionError(action, error);
}

function fileOwnerUserId(file: {
  user?: unknown;
  user_id?: unknown;
}): string {
  const raw = file.user ?? file.user_id;
  if (typeof raw === 'string' && raw.trim()) {
    return raw.trim();
  }
  if (raw && typeof raw === 'object') {
    const rec = raw as { $oid?: unknown; _id?: unknown; id?: unknown };
    const id = rec.$oid ?? rec._id ?? rec.id;
    if (typeof id === 'string' && id.trim()) {
      return id.trim();
    }
  }
  return '';
}

function safeArtifactUrl(raw: string): string | null {
  try {
    const url = new URL(raw, window.location.origin);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.toString() : null;
  } catch {
    return null;
  }
}

function artifactGlyphKind(name: string, kind: string): ArtifactItem['kind'] {
  const value = `${name} ${kind}`.toLowerCase();
  if (/(?:\.html?|html)/.test(value)) {
    return 'html';
  }
  return /(?:\.txt|\.md|text|markdown)/.test(value) ? 'txt' : 'file';
}

function inlineArtifactBlob(body: string, name?: string): Blob {
  if (name && /\.html?$/i.test(name)) {
    return new Blob([body], { type: 'text/html; charset=utf-8' });
  }
  return new Blob([body], { type: 'text/plain;charset=utf-8' });
}

function isHtmlArtifact(artifact: ArtifactItem): boolean {
  return (
    artifact.kind === 'html' ||
    /\.html?$/i.test(artifact.name || '') ||
    /html/i.test(artifact.kindLabel || '')
  );
}

function isImageArtifact(artifact: ArtifactItem, blobType?: string): boolean {
  return (
    /\.(png|jpe?g|gif|webp)$/i.test(artifact.name || '') ||
    /image/i.test(artifact.kindLabel || '') ||
    /image\//i.test(blobType || '')
  );
}

function formatSize(n?: number): string {
  if (n == null || Number.isNaN(n)) {
    return '';
  }
  if (n < 1024) {
    return `${n}B`;
  }
  if (n < 1024 * 1024) {
    return `${(n / 1024).toFixed(1)}KB`;
  }
  return `${(n / (1024 * 1024)).toFixed(1)}MB`;
}

function tokenCount(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0
    ? Math.round(value)
    : null;
}

export function formatRunTokenUsage(run?: PicoRun | null): string | null {
  const usage = run?.token_usage;
  if (!usage) {
    return null;
  }
  // Provider-native usage may use input/output or OpenAI-style prompt/completion.
  const input = tokenCount(usage.input_tokens) ?? tokenCount(usage.prompt_tokens);
  const output = tokenCount(usage.output_tokens) ?? tokenCount(usage.completion_tokens);
  const total =
    tokenCount(usage.total_tokens) ?? (input != null && output != null ? input + output : null);
  const format = (value: number) => value.toLocaleString('zh-CN');
  // Stage #265 T04: always mark token usage as estimate (no billing meters).
  const prefix = '用量（估算）';
  if (input != null && output != null) {
    return `${prefix} · 输入 ${format(input)} · 输出 ${format(output)}${
      total != null ? ` · 共 ${format(total)} tokens` : ''
    }`;
  }
  if (total != null) {
    return `${prefix} · ${format(total)} tokens`;
  }
  return null;
}

function collectArtifacts(messages: TMessage[] | null | undefined): ArtifactItem[] {
  if (!messages?.length) {
    return [];
  }
  const out: ArtifactItem[] = [];
  const seen = new Set<string>();

  for (const m of messages) {
    const files = m.files;
    if (Array.isArray(files)) {
      for (const f of files) {
        const fileId = String(
          (f as { file_id?: string }).file_id ??
            (f as { _id?: string })._id ??
            '',
        );
        const filepath = (f as { filepath?: string }).filepath;
        const id = fileId || (typeof filepath === 'string' ? filepath : '') || String(Math.random());
        if (seen.has(id)) {
          continue;
        }
        seen.add(id);
        const name = String(
          (f as { filename?: string }).filename ?? (f as { name?: string }).name ?? '',
        ).trim();
        const kindLabel = String((f as { type?: string }).type || '').trim() || '附件';
        const bytes =
          (f as { bytes?: number; size?: number }).bytes ?? (f as { size?: number }).size;
        const body = (f as { text?: unknown }).text;
        out.push({
          id,
          name: name || UNNAMED_ATTACHMENT,
          kindLabel,
          sizeLabel: formatSize(typeof bytes === 'number' ? bytes : undefined) || '—',
          kind: artifactGlyphKind(name, kindLabel),
          url: (() => {
            const mapped = picoUploadDownloadUrl(
              typeof filepath === 'string' ? filepath : '',
              fileId || undefined,
              fileOwnerUserId(f),
            );
            return mapped || undefined;
          })(),
          body: typeof body === 'string' ? body : undefined,
        });
      }
    }
  }
  return out;
}

function FileGlyph({ kind }: { kind: ArtifactItem['kind'] }) {
  const label = kind === 'txt' ? 'TXT' : kind === 'html' ? 'HTML' : null;
  return (
    <span
      className={cn(
        'flex h-8 w-8 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold',
        kind === 'txt' || kind === 'html'
          ? 'bg-[#e8f1ff] text-[#3b6fd9]'
          : 'bg-[#f0f0f0] text-[#6b6b6b]',
      )}
      aria-hidden
    >
      {label ? label : <PicoIcon name="file" size="sm" />}
    </span>
  );
}

export default function ResultPanel({
  messages,
  conversationId,
  taskTitle,
  runStatusLabel,
  processHint,
  onClose,
  picoArtifacts,
  runEvents,
  run,
  canRerun,
  rerunning,
  onRerun,
}: {
  messages?: TMessage[] | null;
  conversationId?: string | null;
  taskTitle?: string;
  runStatusLabel?: string;
  processHint?: string | null;
  onClose?: () => void;
  picoArtifacts?: PicoArtifact[] | null;
  runEvents?: PicoRunEvent[] | null;
  run?: PicoRun | null;
  canRerun?: boolean;
  rerunning?: boolean;
  onRerun?: () => void;
}) {
  const [view, setView] = useState<TopView>('web');
  const [expanded, setExpanded] = useState(false);
  const [artifactAction, setArtifactAction] = useState<ArtifactAction | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewImage, setPreviewImage] = useState<string | null>(null);
  const [previewPdf, setPreviewPdf] = useState<string | null>(null);
  const [previewOffice, setPreviewOffice] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const [previewArtifactId, setPreviewArtifactId] = useState<string | null>(null);
  const [localSandbox, setLocalSandbox] = useState<{
    sessionId: string;
    url: string;
    title: string;
    humanCopy: string;
    kind?: string;
  } | null>(null);
  const [websiteError, setWebsiteError] = useState<string | null>(null);
  const [chromeOpen, setChromeOpen] = useState(false);
  const openedWebsiteRef = useRef<string | null>(null);
  const [paneWidth, setPaneWidth] = useState(() =>
    readStoredResultPaneWidth(
      typeof window === 'undefined' ? null : window.localStorage,
      typeof window === 'undefined' ? 1280 : window.innerWidth,
    ),
  );
  const paneWidthRef = useRef(paneWidth);
  paneWidthRef.current = paneWidth;
  const paneZoom = usePaneZoom();
  const tokenUsageLabel = formatRunTokenUsage(run);
  const ledgerSandbox = useMemo(() => collectPicoSandboxSession(runEvents), [runEvents]);
  const sandboxSession = localSandbox || ledgerSandbox;

  useEffect(() => {
    setLocalSandbox(null);
    openedWebsiteRef.current = null;
    setWebsiteError(null);
  }, [conversationId]);
  const previewActive = Boolean(
    previewHtml || previewImage || previewPdf || previewText || previewOffice,
  );
  const messageArts = useMemo(() => collectArtifacts(messages), [messages]);
  const artifacts = useMemo(() => {
    if (picoArtifacts?.length) {
      const mapped = latestArtifactsByFilename(picoArtifacts)
        .filter((artifact) => {
          // Bookkeeping "回复摘要" is not a user download — hide from first-class chips.
          const title = (artifact.title || artifact.user_label || '').trim();
          if (artifact.kind === 'doc' && title === '回复摘要') {
            return false;
          }
          return true;
        })
        .map((artifact) => {
          const name =
            artifact.user_label?.trim() || artifact.title?.trim() || UNNAMED_ARTIFACT;
          const kindLabel = artifact.kind?.trim() || UNKNOWN_KIND;
          const encoding = (artifact.content_encoding || 'utf8').toLowerCase();
          // Binary (base64) must never be treated as UTF-8 text in the panel.
          const body =
            encoding === 'utf8' && typeof artifact.inline === 'string'
              ? artifact.inline
              : undefined;
          const byteSize =
            typeof artifact.byte_size === 'number' && artifact.byte_size >= 0
              ? artifact.byte_size
              : body !== undefined
                ? inlineArtifactBlob(body, name).size
                : undefined;
          return {
            id: artifact.id,
            name,
            kindLabel,
            sizeLabel: formatSize(byteSize) || '—',
            kind: artifactGlyphKind(name, kindLabel),
            url: undefined as string | undefined,
            body,
            picoArtifact: true,
            contentEncoding: encoding,
            byteSize,
            contentSha256: artifact.content_sha256,
          };
        });
      // Filename-first: real files before misc. Keep composer uploads even when
      // the ledger already has generated HTML — otherwise PDF「打开」disappears.
      const seen = new Set(mapped.map((item) => item.id));
      const extras = messageArts.filter((item) => !seen.has(item.id));
      return [...mapped, ...extras].sort((a, b) => {
        const rank = (x: ArtifactItem) =>
          x.kind === 'html' ? 0 : x.kind === 'txt' ? 1 : x.kind === 'file' ? 2 : 3;
        return rank(a) - rank(b) || a.name.localeCompare(b.name, 'zh');
      });
    }
    return messageArts;
  }, [picoArtifacts, messageArts]);

  useEffect(() => {
    if (sandboxSession) {
      setView('web');
    }
  }, [sandboxSession?.sessionId]);

  useEffect(() => {
    paneZoom.reset();
    // Reset scale when the teacher opens a different file or site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewArtifactId, sandboxSession?.sessionId]);

  useEffect(() => {
    const onViewportResize = () => {
      setPaneWidth((current) => clampResultPaneWidth(current, window.innerWidth));
    };
    window.addEventListener('resize', onViewportResize);
    return () => window.removeEventListener('resize', onViewportResize);
  }, []);

  const onResizePointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (expanded) {
      return;
    }
    event.preventDefault();
    const startX = event.clientX;
    const startW = paneWidthRef.current;
    const onMove = (ev: PointerEvent) => {
      const next = clampResultPaneWidth(startW + (startX - ev.clientX), window.innerWidth);
      paneWidthRef.current = next;
      setPaneWidth(next);
    };
    const onUp = () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      try {
        window.localStorage.setItem(RESULT_PANE_WIDTH_STORAGE_KEY, String(paneWidthRef.current));
      } catch {
        /* ignore quota / private mode */
      }
    };
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
  };

  const clearFilePreview = () => {
    setPreviewText(null);
    setPreviewHtml(null);
    setPreviewImage(null);
    setPreviewPdf(null);
    setPreviewOffice(null);
    setPreviewTitle(null);
    setPreviewArtifactId(null);
  };

  const openWebsiteInPane = async (rawUrl: string) => {
    const url = rawUrl.trim();
    if (!url || openedWebsiteRef.current === url) {
      if (url && sandboxSession) {
        setView('web');
      }
      return;
    }
    openedWebsiteRef.current = url;
    setWebsiteError(null);
    clearFilePreview();
    setView('web');
    try {
      const meta = await openPicoSandboxBrowser(url);
      const sessionId = String(meta.session_id || '').trim();
      if (!sessionId.startsWith('sbox_')) {
        throw new Error('sandbox session missing');
      }
      setLocalSandbox({
        sessionId,
        url: String(meta.url || url),
        title: String(meta.title || ''),
        humanCopy: String(meta.human_copy || '请在此画面自行登录，不要在聊天里发送密码'),
        kind: String(meta.kind || 'browser'),
      });
    } catch (err) {
      openedWebsiteRef.current = null;
      const message = err instanceof Error ? err.message : String(err);
      setWebsiteError(
        message.includes('web.denied') || message.includes('denied')
          ? '该地址不能在隔离网页打开'
          : message.includes('quota') || message.includes('已满')
            ? '沙箱已满（最多 8 路）'
            : '打开网页失败，请稍后重试',
      );
    }
  };

  const openOfficeInPane = async (intent: OfficeOpenIntent, artifactId?: string) => {
    const key = `${intent.kind}:${artifactId || intent.filename || 'new'}`;
    if (openedWebsiteRef.current === key && sandboxSession) {
      setView('web');
      return;
    }
    openedWebsiteRef.current = key;
    setWebsiteError(null);
    clearFilePreview();
    setView('web');
    try {
      const match = artifactId
        ? artifacts.find((item) => item.id === artifactId)
        : artifacts.find((item) => {
            const name = item.name || '';
            if (intent.filename && name === intent.filename) {
              return true;
            }
            if (intent.kind === 'writer') {
              return /\.(docx?|odt)$/i.test(name);
            }
            if (intent.kind === 'calc') {
              return /\.(xlsx?|ods)$/i.test(name);
            }
            return /\.(pptx?|odp)$/i.test(name);
          });
      if (!match?.id && !intent.filename) {
        openedWebsiteRef.current = null;
        setWebsiteError('没有可打开的文件。请先生成或上传，再点结果区打开。');
        return;
      }
      const meta = await openPicoSandboxDocument({
        kind: intent.kind,
        artifact_id: match?.id,
        filename: intent.filename || match?.name,
      });
      const sessionId = String(meta.session_id || '').trim();
      if (!sessionId.startsWith('sbox_')) {
        throw new Error('sandbox session missing');
      }
      setLocalSandbox({
        sessionId,
        url: String(meta.url || ''),
        title: String(meta.title || ''),
        humanCopy: String(meta.human_copy || '沙箱已用 LibreOffice 打开这份文档。'),
        kind: String(meta.kind || intent.kind),
      });
    } catch (err) {
      openedWebsiteRef.current = null;
      const message = err instanceof Error ? err.message : String(err);
      setWebsiteError(message.includes('office_unavailable') ? '沙箱还没有装字处理软件' : '打开文档失败，请稍后重试');
    }
  };

  useEffect(() => {
    const office = latestUserOpenOfficeIntent(messages);
    const site = latestUserOpenWebsiteIntent(messages);
    if (ledgerSandbox) {
      if (office) {
        const want = (office.filename || '').toLowerCase();
        const have = `${ledgerSandbox.title || ''} ${ledgerSandbox.url || ''}`.toLowerCase();
        if (!want || have.includes(want.replace(/^.*\//, ''))) {
          return;
        }
        void openOfficeInPane(office);
        return;
      }
      if (site) {
        let already = false;
        try {
          const host = new URL(site).hostname.replace(/^www\./i, '').toLowerCase();
          already = String(ledgerSandbox.url || '').toLowerCase().includes(host);
        } catch {
          already = false;
        }
        if (already) {
          return;
        }
        void openWebsiteInPane(site);
        return;
      }
      return;
    }
    if (office) {
      void openOfficeInPane(office);
      return;
    }
    if (site) {
      void openWebsiteInPane(site);
      return;
    }
    setWebsiteError((prev) =>
      prev && prev.startsWith('没有可打开的文件') ? null : prev,
    );
    // Intent is derived from the latest user turn; skip if ledger already opened.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages, ledgerSandbox]);

  const readArtifactBlob = async (artifact: ArtifactItem, download: boolean): Promise<Blob> => {
    // Binary artifacts always fetch bytes from the content API (bytes-safe).
    if (artifact.picoArtifact && (artifact.contentEncoding === 'base64' || artifact.body === undefined)) {
      return getPicoArtifactContent(artifact.id, download);
    }
    if (artifact.body !== undefined) {
      return inlineArtifactBlob(artifact.body, artifact.name);
    }
    if (artifact.picoArtifact) {
      return getPicoArtifactContent(artifact.id, download);
    }
    throw new Error('artifact content unavailable');
  };

  const dismissOverlayMenus = () => {
    // H7 / R-C: attach menu / dropdown backdrops can sit above the download
    // CTA for one frame. Dismiss floating menus on the download path so the
    // click is never stolen by a leftover backdrop (no pe hack).
    try {
      document.dispatchEvent(
        new KeyboardEvent('keydown', { key: 'Escape', bubbles: true, cancelable: true }),
      );
    } catch {
      /* ignore */
    }
  };

  const applyBlobPreview = async (artifact: ArtifactItem, blob: Blob) => {
    const kind = classifyArtifactPreview(artifact.name, artifact.kindLabel, blob.type);
    setPreviewTitle(artifact.name || '产物预览');
    setPreviewArtifactId(artifact.id);
    if (kind === 'html' || isHtmlArtifact(artifact) || /text\/html/i.test(blob.type || '')) {
      setPreviewHtml(await readBlobText(blob, artifact.body));
      setView('overview');
      return;
    }
    if (kind === 'pdf') {
      // Download route answers octet-stream; re-type so the viewer renders it.
      const bytes =
        blob.type === 'application/pdf' ? blob : new Blob([blob], { type: 'application/pdf' });
      const objectUrl = URL.createObjectURL(bytes);
      setPreviewPdf(objectUrl);
      setView('overview');
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 120_000);
      return;
    }
    if (kind === 'image' || isImageArtifact(artifact, blob.type)) {
      const objectUrl = URL.createObjectURL(blob);
      setPreviewImage(objectUrl);
      setView('overview');
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
      return;
    }
    if (kind === 'office') {
      const officeKind = /\.(pptx?|odp)$/i.test(artifact.name)
        ? 'impress'
        : /\.(xlsx?|ods)$/i.test(artifact.name)
          ? 'calc'
          : 'writer';
      await openOfficeInPane({ kind: officeKind, filename: artifact.name }, artifact.id);
      return;
    }
    if (kind === 'text' || (blob.size <= 512_000 && kind !== 'download')) {
      setPreviewText(await readBlobText(blob, artifact.body));
      setView('overview');
      return;
    }
    const objectUrl = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = objectUrl;
    anchor.download = artifact.name || 'artifact.bin';
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    setArtifactError('无法在线预览该类型产物，已改为下载');
    window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
  };

  const openArtifact = async (artifact: ArtifactItem) => {
    dismissOverlayMenus();
    setArtifactAction({ id: artifact.id, type: 'open' });
    setArtifactError(null);
    clearFilePreview();
    try {
      if (artifact.url) {
        const url = safeArtifactUrl(artifact.url);
        if (!url) {
          throw new Error('invalid artifact URL');
        }
        const parsed = new URL(url);
        if (parsed.origin !== window.location.origin) {
          await openWebsiteInPane(url);
          return;
        }
        const response = await picoAuthedGet(url);
        if (!response.ok) {
          throw new Error(`pico ${response.status}: artifact preview`);
        }
        await applyBlobPreview(artifact, await response.blob());
        return;
      }
      const blob = await readArtifactBlob(artifact, false);
      await applyBlobPreview(artifact, blob);
    } catch (openError) {
      setArtifactError(artifactActionError('open', openError));
    } finally {
      setArtifactAction((current) =>
        current?.id === artifact.id && current.type === 'open' ? null : current,
      );
    }
  };

  const downloadArtifact = async (artifact: ArtifactItem) => {
    dismissOverlayMenus();
    setArtifactAction({ id: artifact.id, type: 'download' });
    setArtifactError(null);
    let objectUrl: string | null = null;
    try {
      const anchor = document.createElement('a');
      if (artifact.url) {
        const url = safeArtifactUrl(artifact.url);
        if (!url) {
          throw new Error('invalid artifact URL');
        }
        const parsed = new URL(url);
        if (parsed.origin === window.location.origin) {
          const response = await picoAuthedGet(url);
          if (!response.ok) {
            throw new Error(`pico ${response.status}: artifact download`);
          }
          objectUrl = URL.createObjectURL(await response.blob());
          anchor.href = objectUrl;
        } else {
          anchor.href = url;
          anchor.rel = 'noopener noreferrer';
          anchor.target = '_blank';
        }
      } else {
        const blob = await readArtifactBlob(artifact, true);
        objectUrl = URL.createObjectURL(blob);
        anchor.href = objectUrl;
      }
      anchor.download = artifact.name || 'artifact.txt';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
    } catch (downloadError) {
      setArtifactError(artifactActionError('download', downloadError));
    } finally {
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
      setArtifactAction((current) =>
        current?.id === artifact.id && current.type === 'download' ? null : current,
      );
    }
  };

  const previewArtifact = previewArtifactId
    ? artifacts.find((item) => item.id === previewArtifactId)
    : undefined;

  const showZoom = Boolean(previewHtml || previewImage);

  return (
    <aside
      className={cn(
        'pico-result-panel relative flex h-full min-w-0 shrink-0 flex-col overflow-x-hidden border-l border-black/[0.06] bg-white text-[#1a1a1a] dark:border-border-light dark:bg-[color:var(--pico-surface)] dark:text-text-primary',
        expanded && 'pico-result-panel--expanded fixed inset-0 z-[200]',
      )}
      style={{ ['--pico-result-w' as string]: `${paneWidth}px` }}
      data-testid="result-panel"
      data-pane-width={paneWidth}
      data-expanded={expanded ? 'true' : 'false'}
      aria-label="结果区"
    >
      {!expanded ? (
        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="调整结果区宽度"
          title="拖动调整宽度"
          data-testid="result-panel-resizer"
          className="absolute inset-y-0 left-0 z-10 hidden w-1.5 cursor-col-resize hover:bg-[#3b6fd9]/25 lg:block"
          onPointerDown={onResizePointerDown}
        />
      ) : null}
      {/* Header — sandbox only. Zoom/fullscreen live in the ⋯ menu. */}
      <div className="flex h-10 items-center gap-1 border-b border-black/[0.06] bg-[#fafafa] px-2 dark:border-border-light dark:bg-[color:var(--pico-surface-2)]">
        <div className="px-2 text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary">
          沙箱
        </div>
        <div className="relative ml-auto flex items-center gap-0.5">
          <button
            type="button"
            className="rounded-md p-1.5 text-[#8c8c8c] hover:bg-black/[0.04]"
            aria-label="沙箱控件"
            aria-expanded={chromeOpen}
            data-testid="result-panel-chrome-menu"
            onClick={() => setChromeOpen((value) => !value)}
          >
            <PicoIcon name="more" size="sm" />
          </button>
          {chromeOpen ? (
            <div
              data-testid="result-panel-chrome-pop"
              className="absolute right-0 top-9 z-20 w-56 rounded-lg border border-black/[0.08] bg-white p-2 shadow-lg dark:border-border-light dark:bg-surface-secondary"
            >
              {showZoom ? (
                <div className="mb-1">
                  <PaneZoomBar
                    label={paneZoom.label}
                    zoomIn={paneZoom.zoomIn}
                    zoomOut={paneZoom.zoomOut}
                    reset={paneZoom.reset}
                  />
                </div>
              ) : null}
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[12px] hover:bg-black/[0.04]"
                aria-label={expanded ? '退出全屏' : '进入全屏'}
                data-testid="result-panel-fullscreen"
                onClick={() => {
                  setExpanded((value) => !value);
                  setChromeOpen(false);
                }}
              >
                <PicoIcon name={expanded ? 'minimize' : 'maximize'} size="sm" />
                {expanded ? '退出全屏' : '进入全屏'}
              </button>
            </div>
          ) : null}
          {onClose ? (
            <button
              type="button"
              className="rounded-md p-1.5 text-[#8c8c8c] hover:bg-black/[0.04]"
              aria-label="收起结果区"
              data-testid="result-panel-close"
              onClick={onClose}
            >
              <PicoIcon name="panel" size="sm" />
            </button>
          ) : null}
        </div>
      </div>

      {/* Body */}
      <div className="flex min-h-0 flex-1 flex-col">
        {artifactError || websiteError ? (
          <p
            className="border-b border-red-100 bg-red-50 px-3 py-2 text-[11.5px] text-red-700"
            role="alert"
            data-testid="artifact-action-error"
          >
            {artifactError || websiteError}
          </p>
        ) : null}
        {previewActive && view !== 'web' ? (
          <div
            className="flex min-h-0 flex-1 flex-col"
            data-testid="artifact-pane-preview"
            data-kind={
              previewHtml !== null
                ? 'html'
                : previewImage !== null
                  ? 'image'
                  : previewOffice !== null
                    ? 'office'
                    : 'text'
            }
          >
            <div className="flex items-center justify-between gap-2 border-b border-black/[0.06] px-2.5 py-1.5">
              <p className="truncate text-[12px] font-medium text-[#3d3d3d]">{previewTitle}</p>
              <div className="flex shrink-0 items-center gap-2">
                {previewArtifact &&
                (previewArtifact.url ||
                  previewArtifact.picoArtifact ||
                  previewArtifact.body !== undefined) ? (
                  <button
                    type="button"
                    data-testid="artifact-download-button"
                    className="text-[11px] font-medium text-[#3d3d3d] underline"
                    aria-label={`下载${previewArtifact.name}`}
                    onClick={() => void downloadArtifact(previewArtifact)}
                    disabled={artifactAction !== null}
                  >
                    下载
                  </button>
                ) : null}
                <button
                  type="button"
                  className="text-[11px] text-[#6b6b6b] underline"
                  onClick={clearFilePreview}
                >
                  关闭预览
                </button>
              </div>
            </div>
            {previewHtml !== null ? (
              <>
                <p className="border-b border-black/[0.04] px-2.5 py-1 text-[10px] text-[#8c8c8c]">
                  安全预览：sandbox 禁用脚本与同源；铺满结果区 · {paneZoom.label}
                </p>
                <div
                  className="relative min-h-0 flex-1 overflow-auto bg-white"
                  data-testid="artifact-html-stage"
                  data-zoom={paneZoom.label}
                  onWheel={paneZoom.onWheel}
                >
                  <div
                    style={{
                      width: `${paneZoom.zoom * 100}%`,
                      height: `${paneZoom.zoom * 100}%`,
                      minHeight: '100%',
                    }}
                  >
                    <iframe
                      title={previewTitle || 'HTML 安全预览'}
                      sandbox=""
                      referrerPolicy="no-referrer"
                      srcDoc={previewHtml}
                      style={{
                        width: `${100 / paneZoom.zoom}%`,
                        height: `${100 / paneZoom.zoom}%`,
                        transform: `scale(${paneZoom.zoom})`,
                        transformOrigin: 'top left',
                      }}
                      className="min-h-full border-0 bg-white"
                      data-testid="artifact-html-iframe"
                    />
                  </div>
                </div>
              </>
            ) : null}
            {previewPdf !== null ? (
              <>
                <p className="border-b border-black/[0.04] px-2.5 py-1 text-[10px] text-[#8c8c8c]">
                  安全预览：内建阅读器 · 不执行文档脚本；铺满结果区
                </p>
                <div className="min-h-0 flex-1 bg-white" data-testid="artifact-pdf-stage">
                  <embed
                    src={previewPdf}
                    type="application/pdf"
                    title={previewTitle || 'PDF 安全预览'}
                    className="h-full w-full border-0"
                    data-testid="artifact-pdf-embed"
                  />
                </div>
              </>
            ) : null}
            {previewImage !== null ? (
              <div
                className="min-h-0 flex-1 overflow-auto bg-[#111]"
                data-testid="artifact-image-stage"
                data-zoom={paneZoom.label}
                onWheel={paneZoom.onWheel}
              >
                <img
                  src={previewImage}
                  alt={previewTitle || 'inspect raster'}
                  style={{ width: `${paneZoom.zoom * 100}%` }}
                  className="mx-auto block h-auto max-w-none bg-white object-contain"
                  data-testid="artifact-image"
                />
              </div>
            ) : null}
            {previewText !== null ? (
              <pre
                className="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words bg-[#fafafa] p-3 text-[12px] leading-relaxed text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary"
                data-testid="artifact-inline-preview"
              >
                {previewText}
              </pre>
            ) : null}
            {previewOffice !== null ? (
              <div
                className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 px-6 text-center"
                data-testid="artifact-office-download"
              >
                <PicoIcon name="file" className="text-[#9a9a9a]" />
                <p className="text-[13px] font-medium text-[#3d3d3d]">{previewTitle}</p>
                <p className="max-w-[16rem] text-[12px] leading-relaxed text-[#6b6b6b]">
                  {previewOffice}
                </p>
              </div>
            ) : null}
          </div>
        ) : (
        <>
        {!sandboxSession && (
          <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
            {taskTitle || runStatusLabel || processHint || tokenUsageLabel ? (
              <div
                className={cn(
                  'mb-3 rounded-lg px-3 py-2',
                  run?.status === 'failed'
                    ? 'bg-[#fdeeee] dark:bg-red-950/30'
                    : run?.status === 'succeeded'
                      ? 'bg-[#eef7ee] dark:bg-emerald-950/20'
                      : run?.status === 'cancelled'
                        ? 'bg-[#f3f3f3] dark:bg-surface-tertiary'
                        : 'bg-[#f0f5ff] dark:bg-surface-tertiary',
                )}
                data-testid="result-status-banner"
              >
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    {taskTitle ? (
                      <p className="truncate text-[13px] font-medium">{taskTitle}</p>
                    ) : null}
                    {runStatusLabel ? (
                      <p
                        className={cn(
                          'mt-0.5 text-[12px]',
                          run?.status === 'failed'
                            ? 'text-[#9a3b3b]'
                            : run?.status === 'succeeded'
                              ? 'text-[#2d6a3e]'
                              : 'text-[#3d3d3d] dark:text-text-secondary',
                        )}
                      >
                        {runStatusLabel}
                      </p>
                    ) : null}
                    {processHint ? (
                      <p
                        className="mt-0.5 truncate text-[12px] text-[#3b6fd9]"
                        data-testid="result-process-hint"
                      >
                        {processHint}
                      </p>
                    ) : null}
                    {tokenUsageLabel ? (
                      <p
                        className="mt-0.5 truncate text-[11px] text-[#6b6b6b] dark:text-text-secondary"
                        data-testid="result-token-usage"
                      >
                        {tokenUsageLabel}
                      </p>
                    ) : null}
                  </div>
                  {canRerun && onRerun ? (
                    <button
                      type="button"
                      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-black/[0.08] bg-white px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d] hover:bg-[#f3f3f3] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-surface-secondary"
                      onClick={onRerun}
                      disabled={rerunning}
                      aria-busy={rerunning || undefined}
                      data-testid="result-panel-rerun"
                    >
                      <PicoIcon name="refresh" size="sm" />
                      {rerunning
                        ? '重新运行中'
                        : run?.status === 'failed'
                          ? '重新运行'
                          : '再跑一次'}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}

            <RunTimeline events={runEvents} run={run} />

            {artifacts.length === 0 ? (
              <div className="flex min-h-[240px] flex-col px-1 pt-2">
                <p className="mb-2 text-[12px] font-medium tracking-normal text-[#8c8c8c]">
                  可下载文件
                </p>
                {runStatusLabel?.includes('等待') &&
                !runStatusLabel?.startsWith('失败') &&
                !runStatusLabel?.startsWith('已停止') ? (
                  <div className="flex flex-1 flex-col justify-center gap-3 rounded-xl border border-black/[0.06] bg-[#fafafa] px-5 py-10 dark:border-border-light dark:bg-surface-tertiary">
                    <RunLoadingIndicator
                      label="执行中，云端继续准备产物"
                      className="justify-center text-[13px] font-medium text-[#3d3d3d] dark:text-text-primary"
                    />
                    <div className="space-y-2" aria-hidden="true">
                      <div className="h-2.5 w-4/5 animate-pulse rounded bg-black/[0.07] dark:bg-white/10" />
                      <div className="h-2.5 w-full animate-pulse rounded bg-black/[0.05] dark:bg-white/[0.08]" />
                      <div className="h-2.5 w-2/3 animate-pulse rounded bg-black/[0.05] dark:bg-white/[0.08]" />
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-black/[0.08] bg-[#fafafa] px-4 py-10 text-[#9a9a9a] dark:border-border-light dark:bg-[color:var(--pico-surface-2)] dark:text-text-secondary">
                    <PicoIcon name="file" className="opacity-30" />
                    <p className="text-[13px] font-medium text-[#6b6b6b]">
                      {runStatusLabel?.startsWith('失败') || runStatusLabel?.startsWith('已停止')
                        ? '本次未产出文件'
                        : '暂无产物'}
                    </p>
                    <p className="max-w-[15rem] text-center text-[11px] leading-relaxed text-[#b0b0b0]">
                      {runStatusLabel?.startsWith('失败')
                        ? '可点击上方「重新运行」再试；过程步骤见上方时间线'
                        : runStatusLabel?.startsWith('已停止')
                          ? '已停止。需要结果时可重新发起任务'
                          : '任务完成后，文件产物会列在这里供打开/下载'}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <ul className="space-y-2" data-testid="human-delivery-chips">
                <li className="list-none px-0.5 pb-1">
                  <p className="text-[12px] font-semibold text-[#1a1a1a] dark:text-text-primary">
                    可下载文件（{artifacts.length}）
                  </p>
                  <p className="text-[11px] leading-relaxed text-[#8c8c8c]">
                    文件名点「打开」铺满本区；Office 只下载，不承诺区内翻页。
                  </p>
                </li>
                {artifacts.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center gap-2 rounded-lg border border-black/[0.06] bg-white px-2.5 py-1.5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] dark:border-border-light dark:bg-surface-secondary"
                    data-testid="human-delivery-chip"
                  >
                    <FileGlyph kind={a.kind} />
                    <div className="min-w-0 flex-1">
                      <p
                        className="truncate text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary"
                        title={a.name}
                      >
                        {a.name}
                      </p>
                      <p className="truncate text-[11px] text-[#9a9a9a]" title={a.kindLabel}>
                        {a.kindLabel} · {a.sizeLabel}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        data-testid="artifact-open-button"
                        className="h-9 rounded-lg border border-black/[0.08] bg-white px-3 text-[12px] font-medium text-[#3d3d3d] hover:bg-[#f7f7f7] disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-light dark:bg-surface-secondary dark:text-text-primary"
                        onClick={() => void openArtifact(a)}
                        disabled={artifactAction !== null}
                        aria-busy={
                          artifactAction?.id === a.id && artifactAction.type === 'open'
                            ? true
                            : undefined
                        }
                      >
                        {artifactAction?.id === a.id && artifactAction.type === 'open'
                          ? '打开中'
                          : '打开'}
                      </button>
                      {a.url || a.picoArtifact || a.body !== undefined ? (
                        <button
                          type="button"
                          data-testid="artifact-download-button"
                          className="inline-flex h-9 items-center gap-1 rounded-lg bg-[#1a1a1a] px-3 text-[12px] font-semibold text-white hover:bg-black disabled:cursor-not-allowed disabled:opacity-60 dark:bg-white dark:text-[#1a1a1a]"
                          onClick={() => void downloadArtifact(a)}
                          disabled={artifactAction !== null}
                          aria-label={`下载${a.name}`}
                          title="下载到本地（路径 /api/pico/v1/artifacts/{id}/content?download=true）"
                          aria-busy={
                            artifactAction?.id === a.id && artifactAction.type === 'download'
                              ? true
                              : undefined
                          }
                        >
                          {artifactAction?.id === a.id && artifactAction.type === 'download' ? (
                            <PicoIcon name="refresh" size="sm" className="animate-spin" />
                          ) : (
                            <PicoIcon name="file" size="sm" />
                          )}
                          下载
                        </button>
                      ) : null}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {view === 'web' && (sandboxSession || artifacts.length === 0) && (
          <div className="flex min-h-0 flex-1 flex-col">
            {sandboxSession ? (
              <SandboxWebPane
                key={sandboxSession.sessionId}
                sessionId={sandboxSession.sessionId}
                initialUrl={sandboxSession.url}
                initialTitle={sandboxSession.title}
                humanCopy={sandboxSession.humanCopy}
                kind={sandboxSession.kind}
                zoom={paneZoom.zoom}
                onWheelZoom={paneZoom.onWheel}
                onZoomIn={paneZoom.zoomIn}
                onZoomOut={paneZoom.zoomOut}
                onZoomReset={paneZoom.reset}
                onDestroyed={() => {
                  openedWebsiteRef.current = null;
                }}
                onReopen={({ url, kind }) => {
                  openedWebsiteRef.current = null;
                  if (url && /^https?:\/\//i.test(url)) {
                    void openWebsiteInPane(url);
                    return;
                  }
                  if (kind && kind !== 'browser' && kind !== 'files') {
                    void openOfficeInPane({
                      kind: kind as OfficeOpenIntent['kind'],
                      filename: sandboxSession.title,
                    });
                    return;
                  }
                  if (url) {
                    void openWebsiteInPane(url);
                  }
                }}
              />
            ) : (
              <div
                className="flex min-h-[240px] flex-1 flex-col items-center justify-center gap-2 px-4 text-center text-[#9a9a9a]"
                data-testid="sandbox-empty"
              >
                <PicoIcon name="link" className="opacity-35" />
                <p className="text-[13px]">沙箱还没有打开窗口</p>
                <p className="max-w-[16rem] text-[11px] leading-relaxed">
                  对 Pico 说「打开 https://example.com」或「打开一份 Word」，右边会出现沙箱里的程序画面。
                </p>
              </div>
            )}
          </div>
        )}

        </>
        )}
      </div>
    </aside>
  );
}
