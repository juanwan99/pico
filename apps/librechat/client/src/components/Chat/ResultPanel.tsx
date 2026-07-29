/**
 * Task-scoped result panel (WorkBuddy-class IA, clean-room).
 * Top views: 概览 / 工作空间文件 / 浏览器
 * 产物 is nested under 概览 (not a 4th top-level tab).
 */
import { useMemo, useState } from 'react';
import {
  ChevronDown,
  ChevronRight,
  FileText,
  FolderOpen,
  Globe,
  Maximize2,
  PanelRightClose,
} from 'lucide-react';
import type { TMessage } from 'librechat-data-provider';
import { cn } from '~/utils';

type TopView = 'overview' | 'files' | 'browser';

type ArtifactItem = {
  id: string;
  name: string;
  kind: string;
};

function collectArtifacts(messages: TMessage[] | null | undefined): ArtifactItem[] {
  if (!messages?.length) {
    return [];
  }
  const out: ArtifactItem[] = [];
  for (const m of messages) {
    const files = m.files;
    if (Array.isArray(files)) {
      for (const f of files) {
        const id = String((f as { file_id?: string }).file_id ?? (f as { _id?: string })._id ?? Math.random());
        const name = String(
          (f as { filename?: string }).filename ?? (f as { name?: string }).name ?? '附件',
        );
        out.push({ id, name, kind: 'file' });
      }
    }
    // content parts with type file/image occasionally
    const content = (m as { content?: unknown[] }).content;
    if (Array.isArray(content)) {
      content.forEach((part, i) => {
        if (part && typeof part === 'object' && 'type' in part) {
          const t = String((part as { type: string }).type);
          if (t.includes('file') || t.includes('image')) {
            out.push({
              id: `${m.messageId}-c${i}`,
              name: t,
              kind: t,
            });
          }
        }
      });
    }
  }
  return out;
}

export default function ResultPanel({
  messages,
  taskTitle,
  runStatusLabel,
  onClose,
}: {
  messages?: TMessage[] | null;
  taskTitle?: string;
  runStatusLabel?: string;
  onClose?: () => void;
}) {
  const [view, setView] = useState<TopView>('overview');
  const [artifactsOpen, setArtifactsOpen] = useState(true);
  const artifacts = useMemo(() => collectArtifacts(messages), [messages]);

  const tabs: { id: TopView; label: string }[] = [
    { id: 'overview', label: '概览' },
    { id: 'files', label: '工作空间文件' },
    { id: 'browser', label: '浏览器' },
  ];

  return (
    <aside
      className="pico-result-panel flex h-full w-[322px] shrink-0 flex-col border-l border-black/[0.06] bg-white text-[#1a1a1a] dark:border-border-light dark:bg-surface-primary dark:text-text-primary"
      data-testid="result-panel"
      aria-label="结果区"
    >
      <div className="flex h-11 items-center gap-1 border-b border-black/[0.06] px-2 dark:border-border-light">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setView(t.id)}
            className={cn(
              'rounded-md px-2.5 py-1.5 text-[12.5px] font-medium transition-colors',
              view === t.id
                ? 'bg-[#edf1f4] text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary'
                : 'text-[#6b6b6b] hover:bg-black/[0.03] hover:text-[#1a1a1a]',
            )}
          >
            {t.label}
          </button>
        ))}
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

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {view === 'overview' && (
          <div className="space-y-3">
            {taskTitle ? (
              <div className="rounded-lg bg-[#fafafa] px-3 py-2 dark:bg-surface-tertiary">
                <p className="text-[11px] text-[#8c8c8c]">当前任务</p>
                <p className="mt-0.5 truncate text-[13px] font-medium">{taskTitle}</p>
                {runStatusLabel ? (
                  <p className="mt-1 text-[12px] text-[#6b6b6b]">{runStatusLabel}</p>
                ) : null}
              </div>
            ) : null}

            <button
              type="button"
              className="flex w-full items-center gap-1.5 rounded-md px-1 py-1 text-left text-[13px] font-medium text-[#1a1a1a] hover:bg-black/[0.03]"
              onClick={() => setArtifactsOpen((v) => !v)}
              aria-expanded={artifactsOpen}
            >
              {artifactsOpen ? (
                <ChevronDown className="h-3.5 w-3.5 text-[#8c8c8c]" />
              ) : (
                <ChevronRight className="h-3.5 w-3.5 text-[#8c8c8c]" />
              )}
              产物
              <span className="ml-auto text-[11px] font-normal text-[#9a9a9a]">
                {artifacts.length || ''}
              </span>
            </button>

            {artifactsOpen && (
              <div className="rounded-lg border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-secondary">
                {artifacts.length === 0 ? (
                  <div className="flex flex-col items-center justify-center gap-2 px-4 py-10 text-[#9a9a9a]">
                    <FileText className="h-8 w-8 opacity-40" strokeWidth={1.25} />
                    <p className="text-[13px]">暂无内容</p>
                  </div>
                ) : (
                  <ul className="divide-y divide-black/[0.04]">
                    {artifacts.map((a) => (
                      <li key={a.id} className="flex items-center gap-2 px-3 py-2.5 text-[13px]">
                        <FileText className="h-4 w-4 shrink-0 text-[#6b6b6b]" />
                        <span className="min-w-0 flex-1 truncate">{a.name}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        )}

        {view === 'files' && (
          <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 text-[#9a9a9a]">
            <FolderOpen className="h-8 w-8 opacity-40" strokeWidth={1.25} />
            <p className="text-[13px]">空目录</p>
            <p className="max-w-[14rem] text-center text-[11px] leading-relaxed text-[#b0b0b0]">
              浏览器版工作空间文件将绑定服务端托管目录（本地全盘后置）
            </p>
          </div>
        )}

        {view === 'browser' && (
          <div className="flex h-full min-h-[200px] flex-col items-center justify-center gap-2 text-[#9a9a9a]">
            <Globe className="h-8 w-8 opacity-40" strokeWidth={1.25} />
            <p className="text-[13px]">暂无连接</p>
          </div>
        )}
      </div>
    </aside>
  );
}
