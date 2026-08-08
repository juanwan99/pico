/**
 * Task result panel — clean-room layout from WorkBuddy nonempty screenshots.
 * Top: view dropdown 概览 | 工作空间文件 | 浏览器
 * 概览: file cards (icon / name / size / 打开); 产物 nested concept = cards list
 * 工作空间文件: search + checkbox rows
 * 浏览器: nav chrome + URL + security footer
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronDown,
  FileText,
  FolderOpen,
  Globe,
  Maximize2,
  Minimize2,
  PanelRightClose,
  ArrowLeft,
  ArrowRight,
  RotateCw,
  ExternalLink,
  Download,
  Loader2,
  Search,
  RotateCcw,
} from 'lucide-react';
import type { TMessage } from 'librechat-data-provider';
import {
  getPicoArtifactContent,
  type PicoArtifact,
  type PicoRun,
  type PicoRunEvent,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';
import RunLoadingIndicator from './RunLoadingIndicator';
import RunTimeline from './RunTimeline';

type TopView = 'overview' | 'files' | 'browser';

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
  const verb = action === 'open' ? '打开' : '下载';
  const message = error instanceof Error ? error.message : String(error);
  const pathHint =
    '正确路径：结果区「下载」按钮，或 GET /api/pico/v1/artifacts/{id}/content?download=true（勿用虚构 /download 尾缀）';
  if (message.includes('401')) {
    return `${verb}产物失败：登录已失效，请刷新页面后重新登录。${pathHint}`;
  }
  if (message.includes('403') || message.includes('404')) {
    return `${verb}产物失败：产物不存在或无权限。${pathHint}`;
  }
  if (message.includes('502') || message.includes('unavailable')) {
    return `${verb}产物失败：产物服务暂时不可用，请稍后重试。${pathHint}`;
  }
  return `${verb}产物失败，请稍后重试。${pathHint}`;
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
        const id = String(
          (f as { file_id?: string }).file_id ??
            (f as { _id?: string })._id ??
            (f as { filepath?: string }).filepath ??
            Math.random(),
        );
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
          url: (f as { filepath?: string; preview?: string }).filepath,
          body: typeof body === 'string' ? body : undefined,
        });
      }
    }
  }
  return out;
}

const VIEW_LABEL: Record<TopView, string> = {
  overview: '概览',
  files: '工作空间文件',
  browser: '浏览器',
};

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
      {label ? label : <FileText className="h-4 w-4" />}
    </span>
  );
}

export default function ResultPanel({
  messages,
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
  const [view, setView] = useState<TopView>('overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const [fileQuery, setFileQuery] = useState('');
  const [browserUrl, setBrowserUrl] = useState('');
  const [browserLoaded, setBrowserLoaded] = useState('');
  const [browserKey, setBrowserKey] = useState(0);
  const [browserHistory, setBrowserHistory] = useState<string[]>([]);
  const [browserIndex, setBrowserIndex] = useState(-1);
  const [expanded, setExpanded] = useState(false);
  const [artifactAction, setArtifactAction] = useState<ArtifactAction | null>(null);
  const [artifactError, setArtifactError] = useState<string | null>(null);
  const [previewText, setPreviewText] = useState<string | null>(null);
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [previewTitle, setPreviewTitle] = useState<string | null>(null);
  const navigate = useNavigate();
  const tokenUsageLabel = formatRunTokenUsage(run);
  const messageArts = useMemo(() => collectArtifacts(messages), [messages]);
  const artifacts = useMemo(() => {
    if (picoArtifacts?.length) {
      const mapped = picoArtifacts
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
      // Filename-first: real files before misc.
      return mapped.sort((a, b) => {
        const rank = (x: ArtifactItem) =>
          x.kind === 'html' ? 0 : x.kind === 'txt' ? 1 : x.kind === 'file' ? 2 : 3;
        return rank(a) - rank(b) || a.name.localeCompare(b.name, 'zh');
      });
    }
    return messageArts;
  }, [picoArtifacts, messageArts]);

  // Prefer https links in artifact inline as browser targets
  useEffect(() => {
    const fromArts = (picoArtifacts || []).find((a) => {
      const s = (a.inline || a.title || '').trim();
      return /^https?:\/\//i.test(s);
    });
    if (fromArts) {
      const u = (fromArts.inline || fromArts.title || '').trim();
      setBrowserUrl(u);
      setBrowserLoaded(u);
      setBrowserHistory([u]);
      setBrowserIndex(0);
    }
  }, [picoArtifacts]);

  const filteredFiles = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) {
      return artifacts;
    }
    return artifacts.filter((a) => a.name.toLowerCase().includes(q));
  }, [artifacts, fileQuery]);

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

  const openArtifact = async (artifact: ArtifactItem) => {
    dismissOverlayMenus();
    setArtifactAction({ id: artifact.id, type: 'open' });
    setArtifactError(null);
    setPreviewText(null);
    setPreviewHtml(null);
    setPreviewTitle(null);
    try {
      if (artifact.url) {
        const url = safeArtifactUrl(artifact.url);
        if (!url) {
          throw new Error('invalid artifact URL');
        }
        const opened = window.open(url, '_blank', 'noopener,noreferrer');
        if (!opened) {
          throw new Error('artifact preview blocked');
        }
        return;
      }
      const blob = await readArtifactBlob(artifact, false);
      // HTML: sandboxed iframe preview (no scripts / no same-origin / no forms).
      if (isHtmlArtifact(artifact) || /text\/html/i.test(blob.type || '')) {
        const text = await blob.text();
        setPreviewTitle(artifact.name || 'HTML 预览');
        setPreviewHtml(text);
        return;
      }
      // In-panel preview for text — no popup dependency (W4: open must show content).
      const looksText =
        artifact.kind === 'txt' ||
        /text|json|markdown|plain/i.test(blob.type || '') ||
        /\.(txt|md|json|csv|log)$/i.test(artifact.name || '');
      // Binary Office packages: do not force as UTF-8 text preview.
      const looksBinaryOffice = /\.(docx|pptx|xlsx)$/i.test(artifact.name || '');
      if ((looksText || (blob.size <= 512_000 && !looksBinaryOffice)) && !looksBinaryOffice) {
        const text = await blob.text();
        setPreviewTitle(artifact.name || '产物预览');
        setPreviewText(text);
        return;
      }
      // Office / large binary: download-friendly open fallback with clear message.
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = objectUrl;
      anchor.download = artifact.name || 'artifact.bin';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setArtifactError(
        looksBinaryOffice
          ? '该 Office 产物已触发下载；请用 Word/PowerPoint/LibreOffice 打开验证'
          : '无法在线预览该类型产物，已改为下载',
      );
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
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
        anchor.href = url;
        anchor.rel = 'noopener noreferrer';
        anchor.target = '_blank';
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

  const loadBrowserUrl = (raw: string) => {
    const value = raw.trim();
    if (!value) {
      return;
    }
    const next = /^https?:\/\//i.test(value) ? value : `https://${value}`;
    try {
      const parsed = new URL(next);
      if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
        return;
      }
    } catch {
      return;
    }
    const history = [...browserHistory.slice(0, browserIndex + 1), next];
    setBrowserUrl(next);
    setBrowserLoaded(next);
    setBrowserHistory(history);
    setBrowserIndex(history.length - 1);
  };

  const moveBrowserHistory = (delta: number) => {
    const nextIndex = browserIndex + delta;
    const next = browserHistory[nextIndex];
    if (!next || nextIndex < 0 || nextIndex >= browserHistory.length) {
      return;
    }
    setBrowserIndex(nextIndex);
    setBrowserUrl(next);
    setBrowserLoaded(next);
  };

  return (
    <aside
      className={cn(
        'pico-result-panel flex h-full w-[340px] shrink-0 flex-col border-l border-black/[0.06] bg-white text-[#1a1a1a] dark:border-border-light dark:bg-surface-primary dark:text-text-primary',
        expanded && 'pico-result-panel--expanded fixed inset-0 z-[200]',
      )}
      data-testid="result-panel"
      aria-label="结果区"
    >
      {/* Header — dropdown view switcher (matches nonempty shots) */}
      <div className="flex h-11 items-center gap-1 border-b border-black/[0.06] bg-[#fafafa] px-2 dark:border-border-light">
        <div className="relative">
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-[13px] font-medium text-[#1a1a1a] hover:bg-black/[0.04] dark:text-text-primary"
            onClick={() => setMenuOpen((v) => !v)}
            aria-expanded={menuOpen}
            aria-haspopup="listbox"
          >
            {VIEW_LABEL[view]}
            <ChevronDown className="h-3.5 w-3.5 text-[#8c8c8c]" />
          </button>
          {menuOpen && (
            <>
              <button
                type="button"
                className="fixed inset-0 z-40 cursor-default"
                aria-label="close"
                onClick={() => setMenuOpen(false)}
              />
              <ul
                className="absolute left-0 top-full z-50 mt-1 w-40 overflow-hidden rounded-xl border border-black/[0.08] bg-white py-1 shadow-lg dark:border-border-light dark:bg-surface-secondary"
                role="listbox"
              >
                {(Object.keys(VIEW_LABEL) as TopView[]).map((id) => (
                  <li key={id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={view === id}
                      className={cn(
                        'flex w-full px-3 py-2 text-left text-[13px]',
                        view === id ? 'bg-[#edf1f4] font-medium' : 'hover:bg-black/[0.03]',
                      )}
                      onClick={() => {
                        setView(id);
                        setMenuOpen(false);
                      }}
                    >
                      {VIEW_LABEL[id]}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
        <div className="ml-auto flex items-center gap-0.5">
          <button
            type="button"
            className="rounded-md p-1.5 text-[#8c8c8c] hover:bg-black/[0.04]"
            aria-label={expanded ? '退出全屏' : '进入全屏'}
            title={expanded ? '退出全屏' : '进入全屏'}
            onClick={() => setExpanded((value) => !value)}
          >
            {expanded ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </button>
          {onClose ? (
            <button
              type="button"
              className="rounded-md p-1.5 text-[#8c8c8c] hover:bg-black/[0.04]"
              aria-label="收起结果区"
              onClick={onClose}
            >
              <PanelRightClose className="h-3.5 w-3.5" />
            </button>
          ) : null}
        </div>
      </div>

      {/* Body */}
      <div className="flex min-h-0 flex-1 flex-col">
        {previewHtml !== null ? (
          <div
            className="mb-2 rounded-lg border border-black/[0.08] bg-white p-2 dark:border-border-light dark:bg-surface-secondary"
            data-testid="artifact-html-preview"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="truncate text-[12px] font-medium text-[#3d3d3d]">{previewTitle}</p>
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
            <p className="mb-1 text-[10px] text-[#8c8c8c]">
              安全预览：sandbox 禁用脚本与同源；CSP 禁止外联
            </p>
            {/* empty sandbox = max restriction (no scripts, same-origin, forms, popups) */}
            <iframe
              title={previewTitle || 'HTML 安全预览'}
              sandbox=""
              referrerPolicy="no-referrer"
              srcDoc={previewHtml}
              className="h-64 w-full rounded border border-black/[0.06] bg-white"
              data-testid="artifact-html-iframe"
            />
          </div>
        ) : null}
        {previewText !== null ? (
          <div
            className="mb-2 rounded-lg border border-black/[0.08] bg-white p-2 dark:border-border-light dark:bg-surface-secondary"
            data-testid="artifact-inline-preview"
          >
            <div className="mb-1 flex items-center justify-between gap-2">
              <p className="truncate text-[12px] font-medium text-[#3d3d3d]">{previewTitle}</p>
              <button
                type="button"
                className="text-[11px] text-[#6b6b6b] underline"
                onClick={() => {
                  setPreviewText(null);
                  setPreviewTitle(null);
                }}
              >
                关闭预览
              </button>
            </div>
            <pre className="max-h-64 overflow-auto whitespace-pre-wrap break-words rounded bg-[#fafafa] p-2 text-[12px] leading-relaxed text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary">
              {previewText}
            </pre>
          </div>
        ) : null}
        {artifactError ? (
          <p
            className="border-b border-red-100 bg-red-50 px-3 py-2 text-[11.5px] text-red-700"
            role="alert"
            data-testid="artifact-action-error"
          >
            {artifactError}
          </p>
        ) : null}
        {view === 'overview' && (
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
                      <RotateCcw className="h-3 w-3" />
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
                {runStatusLabel?.includes('等待') ? (
                  <div className="flex flex-1 flex-col justify-center gap-3 rounded-xl border border-black/[0.06] bg-[#fafafa] px-5 py-10 dark:border-border-light dark:bg-surface-tertiary">
                    <RunLoadingIndicator
                      label="执行中，正在准备产物"
                      className="justify-center text-[13px] font-medium text-[#3d3d3d] dark:text-text-primary"
                    />
                    <div className="space-y-2" aria-hidden="true">
                      <div className="h-2.5 w-4/5 animate-pulse rounded bg-black/[0.07] dark:bg-white/10" />
                      <div className="h-2.5 w-full animate-pulse rounded bg-black/[0.05] dark:bg-white/[0.08]" />
                      <div className="h-2.5 w-2/3 animate-pulse rounded bg-black/[0.05] dark:bg-white/[0.08]" />
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-black/[0.08] bg-[#fafafa] px-4 py-10 text-[#9a9a9a]">
                    <FileText className="h-9 w-9 opacity-30" strokeWidth={1.25} />
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
                    文件名可点「下载」到本机；HTML 用浏览器打开。不以 ID 为主标签。
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
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Download className="h-3.5 w-3.5" />
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

        {view === 'files' && (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="border-b border-black/[0.05] px-3 py-2">
              <div className="flex items-center gap-2 rounded-lg bg-[#f5f5f5] px-2.5 py-1.5 dark:bg-surface-tertiary">
                <Search className="h-3.5 w-3.5 shrink-0 text-[#9a9a9a]" />
                <input
                  value={fileQuery}
                  onChange={(e) => setFileQuery(e.target.value)}
                  placeholder="搜索文件"
                  className="w-full bg-transparent text-[13px] outline-none placeholder:text-[#b0b0b0]"
                />
              </div>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto">
              {filteredFiles.length === 0 ? (
                <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 text-[#9a9a9a]">
                  <FolderOpen className="h-8 w-8 opacity-35" strokeWidth={1.25} />
                  <p className="text-[13px]">空目录</p>
                </div>
              ) : (
                <ul>
                  {filteredFiles.map((a) => (
                    <li
                      key={a.id}
                      className="flex items-center gap-2 border-b border-black/[0.04] px-3 py-2.5 hover:bg-[#fafafa] dark:hover:bg-surface-tertiary"
                    >
                      <input
                        type="checkbox"
                        className="rounded border-black/20"
                        aria-label={a.name}
                      />
                      <FileGlyph kind={a.kind} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-[13px]" title={a.name}>
                          {a.name}
                        </span>
                        <span
                          className="block truncate text-[11px] text-[#9a9a9a]"
                          title={a.kindLabel}
                        >
                          {a.kindLabel} · {a.sizeLabel}
                        </span>
                      </span>
                      <button
                        type="button"
                        className="rounded-md px-2 py-1 text-[11.5px] font-medium text-[#3d3d3d] hover:bg-[#f0f0f0]"
                        onClick={() => void openArtifact(a)}
                        disabled={artifactAction !== null}
                      >
                        {artifactAction?.id === a.id && artifactAction.type === 'open'
                          ? '打开中'
                          : '打开'}
                      </button>
                      {a.url || a.picoArtifact || a.body !== undefined ? (
                        <button
                          type="button"
                          data-testid="artifact-download-button"
                          className="inline-flex items-center gap-1 rounded-md bg-[#1a1a1a] px-2.5 py-1 text-[11.5px] font-semibold text-white hover:bg-black disabled:opacity-50 dark:bg-white dark:text-[#1a1a1a]"
                          onClick={() => void downloadArtifact(a)}
                          disabled={artifactAction !== null}
                          aria-label={`下载${a.name}`}
                          title="下载到本地（/api/pico/v1/artifacts/{id}/content?download=true）"
                        >
                          <Download className="h-3 w-3" />
                          {artifactAction?.id === a.id && artifactAction.type === 'download'
                            ? '下载中'
                            : '下载'}
                        </button>
                      ) : null}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        )}

        {view === 'browser' && (
          <div className="flex min-h-0 flex-1 flex-col">
            <div className="flex items-center gap-1 border-b border-black/[0.05] px-2 py-1.5">
              <button
                type="button"
                className="rounded p-1 text-[#8c8c8c] disabled:opacity-35"
                aria-label="后退"
                disabled={browserIndex <= 0}
                onClick={() => moveBrowserHistory(-1)}
              >
                <ArrowLeft className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                className="rounded p-1 text-[#8c8c8c] disabled:opacity-35"
                aria-label="前进"
                disabled={browserIndex < 0 || browserIndex >= browserHistory.length - 1}
                onClick={() => moveBrowserHistory(1)}
              >
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                className="rounded p-1 text-[#8c8c8c]"
                aria-label="刷新"
                onClick={() => setBrowserKey((k) => k + 1)}
              >
                <RotateCw className="h-3.5 w-3.5" />
              </button>
              <form
                className="mx-1 flex min-w-0 flex-1 items-center rounded-full bg-[#f3f3f3] px-3 py-1 dark:bg-surface-tertiary"
                onSubmit={(e) => {
                  e.preventDefault();
                  const raw = browserUrl.trim();
                  if (!raw) {
                    return;
                  }
                  loadBrowserUrl(raw);
                }}
              >
                <input
                  value={browserUrl}
                  onChange={(e) => setBrowserUrl(e.target.value)}
                  placeholder="输入网址后回车预览"
                  className="w-full bg-transparent text-[12px] outline-none placeholder:text-[#b0b0b0]"
                />
              </form>
              <button
                type="button"
                className="rounded p-1 text-[#8c8c8c]"
                aria-label="在新窗口打开"
                onClick={() => {
                  const raw = (browserLoaded || browserUrl).trim();
                  if (raw) {
                    const u = /^https?:\/\//i.test(raw) ? raw : `https://${raw}`;
                    window.open(u, '_blank', 'noopener,noreferrer');
                  }
                }}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
            </div>
            {browserLoaded ? (
              <iframe
                key={browserKey}
                title="browser-preview"
                src={browserLoaded}
                sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                className="min-h-0 w-full flex-1 border-0 bg-white"
              />
            ) : (
              <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 bg-[#fafafa] px-4 text-center text-[#9a9a9a] dark:bg-presentation">
                <Globe className="h-8 w-8 opacity-35" strokeWidth={1.25} />
                <p className="text-[13px]">输入网址并回车可内嵌预览</p>
                <p className="max-w-[14rem] text-[11px] leading-relaxed">
                  部分站点禁止嵌入；若空白请用右上角新窗口打开
                </p>
                <div className="mt-2 flex flex-wrap justify-center gap-1.5">
                  {['example.com', 'www.wikipedia.org'].map((host) => (
                    <button
                      key={host}
                      type="button"
                      className="rounded-full bg-white px-2.5 py-1 text-[11px] ring-1 ring-black/[0.06]"
                      onClick={() => {
                        loadBrowserUrl(host);
                      }}
                    >
                      {host}
                    </button>
                  ))}
                </div>
              </div>
            )}
            <div className="border-t border-black/[0.05] px-3 py-2 text-center text-[11px] leading-snug text-[#9a9a9a]">
              预览仅供参考，注意信息安全；敏感操作请在受信浏览器中完成
            </div>
          </div>
        )}
      </div>
      <div className="shrink-0 border-t border-black/[0.06] px-3 py-2 dark:border-border-light">
        <button
          type="button"
          onClick={() => navigate('/more/files')}
          className="w-full rounded-lg bg-[#f5f5f5] py-1.5 text-center text-[12px] font-medium text-[#3d3d3d] hover:bg-[#ebebeb] dark:bg-surface-tertiary dark:text-text-primary"
        >
          打开我的文件
        </button>
      </div>
    </aside>
  );
}
