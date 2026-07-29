/**
 * Task result panel — clean-room layout from WorkBuddy nonempty screenshots.
 * Top: view dropdown 概览 | 工作空间文件 | 浏览器
 * 概览: file cards (icon / name / size / 打开); 产物 nested concept = cards list
 * 工作空间文件: search + checkbox rows
 * 浏览器: nav chrome + URL + security footer
 */
import { useMemo, useState } from 'react';
import {
  ChevronDown,
  FileText,
  FolderOpen,
  Globe,
  Maximize2,
  PanelRightClose,
  ArrowLeft,
  ArrowRight,
  RotateCw,
  ExternalLink,
  MoreHorizontal,
  Search,
} from 'lucide-react';
import type { TMessage } from 'librechat-data-provider';
import type { PicoArtifact } from '~/data-provider/pico/api';
import { cn } from '~/utils';

type TopView = 'overview' | 'files' | 'browser';

type ArtifactItem = {
  id: string;
  name: string;
  sizeLabel: string;
  kind: 'txt' | 'file' | 'other';
  url?: string;
  body?: string;
};

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
          (f as { filename?: string }).filename ??
            (f as { name?: string }).name ??
            '附件',
        );
        const bytes = (f as { bytes?: number; size?: number }).bytes ?? (f as { size?: number }).size;
        const lower = name.toLowerCase();
        out.push({
          id,
          name,
          sizeLabel: formatSize(typeof bytes === 'number' ? bytes : undefined) || '—',
          kind: lower.endsWith('.txt') || lower.endsWith('.md') ? 'txt' : 'file',
          url: (f as { filepath?: string; preview?: string }).filepath,
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
  return (
    <span
      className={cn(
        'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-[10px] font-bold',
        kind === 'txt'
          ? 'bg-[#e8f1ff] text-[#3b6fd9]'
          : 'bg-[#f0f0f0] text-[#6b6b6b]',
      )}
      aria-hidden
    >
      {kind === 'txt' ? 'TXT' : <FileText className="h-4 w-4" />}
    </span>
  );
}

export default function ResultPanel({
  messages,
  taskTitle,
  runStatusLabel,
  onClose,
  picoArtifacts,
}: {
  messages?: TMessage[] | null;
  taskTitle?: string;
  runStatusLabel?: string;
  onClose?: () => void;
  picoArtifacts?: PicoArtifact[] | null;
}) {
  const [view, setView] = useState<TopView>('overview');
  const [menuOpen, setMenuOpen] = useState(false);
  const [fileQuery, setFileQuery] = useState('');
  const [browserUrl, setBrowserUrl] = useState('');
  const messageArts = useMemo(() => collectArtifacts(messages), [messages]);
  const artifacts = useMemo(() => {
    if (picoArtifacts?.length) {
      return picoArtifacts.map((a) => ({
        id: a.id,
        name: a.title || a.kind || '产物',
        sizeLabel: a.inline ? `${Math.min(a.inline.length, 9999)}B` : '—',
        kind: (a.title || '').toLowerCase().endsWith('.txt') ? ('txt' as const) : ('file' as const),
        url: undefined as string | undefined,
        body: a.inline,
      }));
    }
    return messageArts;
  }, [picoArtifacts, messageArts]);

  const filteredFiles = useMemo(() => {
    const q = fileQuery.trim().toLowerCase();
    if (!q) {
      return artifacts;
    }
    return artifacts.filter((a) => a.name.toLowerCase().includes(q));
  }, [artifacts, fileQuery]);

  const openArtifact = (a: ArtifactItem & { body?: string }) => {
    if (a.url) {
      // only allow http(s) relative-safe opens
      try {
        const u = new URL(a.url, window.location.origin);
        if (u.protocol !== 'http:' && u.protocol !== 'https:') {
          return;
        }
        window.open(u.toString(), '_blank', 'noopener,noreferrer');
      } catch {
        /* ignore */
      }
      return;
    }
    if (a.body) {
      const w = window.open('', '_blank');
      if (w) {
        w.document.title = a.name || '产物';
        const pre = w.document.createElement('pre');
        pre.style.cssText = 'white-space:pre-wrap;font:14px/1.5 system-ui;padding:16px;margin:0';
        pre.textContent = a.body; // textContent — no HTML injection
        w.document.body.appendChild(pre);
      }
    }
  };

  return (
    <aside
      className="pico-result-panel flex h-full w-[322px] shrink-0 flex-col border-l border-black/[0.06] bg-white text-[#1a1a1a] dark:border-border-light dark:bg-surface-primary dark:text-text-primary"
      data-testid="result-panel"
      aria-label="结果区"
    >
      {/* Header — dropdown view switcher (matches nonempty shots) */}
      <div className="flex h-11 items-center gap-1 border-b border-black/[0.06] px-2 dark:border-border-light">
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
                        view === id
                          ? 'bg-[#edf1f4] font-medium'
                          : 'hover:bg-black/[0.03]',
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
            aria-label="进入全屏"
            title="进入全屏"
          >
            <Maximize2 className="h-3.5 w-3.5" />
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
        {view === 'overview' && (
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            {taskTitle || runStatusLabel ? (
              <div className="mb-3 rounded-lg bg-[#fafafa] px-3 py-2 dark:bg-surface-tertiary">
                {taskTitle ? (
                  <p className="truncate text-[13px] font-medium">{taskTitle}</p>
                ) : null}
                {runStatusLabel ? (
                  <p className="mt-0.5 text-[12px] text-[#6b6b6b]">{runStatusLabel}</p>
                ) : null}
              </div>
            ) : null}

            {artifacts.length === 0 ? (
              <div className="flex min-h-[220px] flex-col items-center justify-center gap-2 text-[#9a9a9a]">
                <FileText className="h-8 w-8 opacity-35" strokeWidth={1.25} />
                <p className="text-[13px]">
                  {runStatusLabel?.includes('等待')
                    ? '任务进行中，产物生成后将显示在这里'
                    : runStatusLabel?.startsWith('失败')
                      ? '本次运行未产出文件（见上方状态）'
                      : '暂无内容'}
                </p>
                <p className="max-w-[14rem] text-center text-[11px] leading-relaxed text-[#b0b0b0]">
                  模型回复摘要与工具产物会自动记入账本，并出现在本列表
                </p>
              </div>
            ) : (
              <ul className="space-y-2">
                {artifacts.map((a) => (
                  <li
                    key={a.id}
                    className="flex items-center gap-2.5 rounded-xl border border-black/[0.06] bg-white px-2.5 py-2 shadow-[0_1px_2px_rgba(0,0,0,0.03)] dark:border-border-light dark:bg-surface-secondary"
                  >
                    <FileGlyph kind={a.kind} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary">
                        {a.name}
                      </p>
                      {a.sizeLabel ? (
                        <p className="text-[11px] text-[#9a9a9a]">{a.sizeLabel}</p>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      className="shrink-0 rounded-lg bg-[#f3f3f3] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d] hover:bg-[#e8e8e8] dark:bg-surface-tertiary dark:text-text-primary"
                      onClick={() => openArtifact(a)}
                    >
                      打开
                    </button>
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
                      <input type="checkbox" className="rounded border-black/20" aria-label={a.name} />
                      <FileGlyph kind={a.kind} />
                      <span className="min-w-0 flex-1 truncate text-[13px]">{a.name}</span>
                      <span className="shrink-0 text-[12px] text-[#9a9a9a]">{a.sizeLabel}</span>
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
              <button type="button" className="rounded p-1 text-[#8c8c8c]" aria-label="后退" disabled>
                <ArrowLeft className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="rounded p-1 text-[#8c8c8c]" aria-label="前进" disabled>
                <ArrowRight className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="rounded p-1 text-[#8c8c8c]" aria-label="刷新">
                <RotateCw className="h-3.5 w-3.5" />
              </button>
              <form
                className="mx-1 flex min-w-0 flex-1 items-center rounded-full bg-[#f3f3f3] px-3 py-1 dark:bg-surface-tertiary"
                onSubmit={(e) => {
                  e.preventDefault();
                }}
              >
                <input
                  value={browserUrl}
                  onChange={(e) => setBrowserUrl(e.target.value)}
                  placeholder="搜索或输入网址"
                  className="w-full bg-transparent text-[12px] outline-none placeholder:text-[#b0b0b0]"
                />
              </form>
              <button
                type="button"
                className="rounded p-1 text-[#8c8c8c]"
                aria-label="在新窗口打开"
                onClick={() => {
                  if (browserUrl.trim()) {
                    const u = browserUrl.startsWith('http') ? browserUrl : `https://${browserUrl}`;
                    window.open(u, '_blank', 'noopener,noreferrer');
                  }
                }}
              >
                <ExternalLink className="h-3.5 w-3.5" />
              </button>
              <button type="button" className="rounded p-1 text-[#8c8c8c]" aria-label="更多">
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="flex min-h-0 flex-1 flex-col items-center justify-center bg-[#fafafa] text-[#9a9a9a] dark:bg-presentation">
              <Globe className="mb-2 h-8 w-8 opacity-35" strokeWidth={1.25} />
              <p className="text-[13px]">暂无连接</p>
            </div>
            <div className="border-t border-black/[0.05] px-3 py-2 text-center text-[11px] leading-snug text-[#9a9a9a]">
              当前页面由 AI 操作，请注意信息安全；若有疑问，请立即结束任务
            </div>
          </div>
        )}
      </div>
    </aside>
  );
}
