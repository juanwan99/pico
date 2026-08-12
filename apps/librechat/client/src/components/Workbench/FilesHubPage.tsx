/**
 * Global artifact ledger with truthful preview and download capabilities.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Download, Eye, Loader2, RefreshCw, Search, X } from 'lucide-react';
import {
  getPicoArtifactContent,
  getPicoTask,
  listPicoTasks,
  type PicoArtifact,
} from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import { cn } from '~/utils';

type Row = PicoArtifact & {
  key: string;
  taskId: string;
  taskTitle: string;
  taskCreatedAt?: string | null;
};

type FileGroup = 'all' | 'document' | 'code' | 'data' | 'other';

const GROUP_LABELS: Record<FileGroup, string> = {
  all: '全部类型',
  document: '文档',
  code: '代码',
  data: '数据',
  other: '其他',
};

const EXTENSION_GROUPS: Record<Exclude<FileGroup, 'all'>, string[]> = {
  document: ['txt', 'md', 'doc', 'docx', 'pdf', 'rtf'],
  code: ['js', 'jsx', 'ts', 'tsx', 'py', 'java', 'go', 'rs', 'html', 'css', 'sh', 'sql'],
  data: ['json', 'csv', 'tsv', 'xls', 'xlsx', 'xml', 'yaml', 'yml'],
  other: [],
};

const PREVIEW_LIMIT = 100_000;

function getExtension(title: string) {
  const match = title
    .trim()
    .toLowerCase()
    .match(/\.([a-z0-9]+)$/);
  return match?.[1] || '';
}

function getFileGroup(row: PicoArtifact): Exclude<FileGroup, 'all'> {
  const extension = getExtension(row.title || '');
  for (const [group, extensions] of Object.entries(EXTENSION_GROUPS)) {
    if (extensions.includes(extension)) {
      return group as Exclude<FileGroup, 'all'>;
    }
  }
  if (row.kind === 'doc') {
    return 'document';
  }
  if (row.kind === 'code') {
    return 'code';
  }
  return 'other';
}

function getTypeLabel(row: PicoArtifact) {
  const extension = getExtension(row.title || '');
  return extension ? extension.toUpperCase() : row.kind?.toUpperCase() || 'FILE';
}

function getInlineBytes(inline?: string) {
  if (typeof inline !== 'string') {
    return null;
  }
  return new Blob([inline]).size;
}

function formatBytes(bytes: number | null) {
  if (bytes == null) {
    return '大小未知';
  }
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(bytes < 10 * 1024 ? 1 : 0)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(value?: string | null) {
  if (!value) {
    return '时间未知';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '时间未知';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function FileTypeIcon({ group }: { group: Exclude<FileGroup, 'all'> }) {
  const icon: PicoIconName = group === 'code' ? 'blocks' : group === 'data' ? 'chart' : 'doc';
  return <PicoIcon name={icon} size="sm" />;
}

export default function FilesHubPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState<FileGroup>('all');

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    setWarning(null);
    try {
      const { tasks } = await listPicoTasks();
      const taskList = (tasks || []).slice(0, 30);
      const details = await Promise.all(
        taskList.map(async (task) => {
          try {
            return { task, detail: await getPicoTask(task.id), failed: false };
          } catch {
            return { task, detail: null, failed: true };
          }
        }),
      );
      const failedCount = details.filter((item) => item.failed).length;
      const nextRows = details.flatMap(({ task, detail }) =>
        (detail?.artifacts || [])
          .filter((artifact) => !(artifact.kind === 'doc' && artifact.title === '回复摘要'))
          .map((artifact) => ({
            ...artifact,
            key: `${task.id}:${artifact.id}`,
            taskId: task.id,
            taskTitle: task.title || '未命名任务',
            taskCreatedAt: task.created_at,
          })),
      );
      setRows(nextRows);
      setSelectedKey((current) =>
        nextRows.some((row) => row.key === current) ? current : (nextRows[0]?.key ?? null),
      );
      if (failedCount > 0) {
        setWarning(`${failedCount} 个任务的产物暂时无法读取，已展示其余文件`);
      }
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : String(fetchError));
      setRows([]);
      setSelectedKey(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return rows.filter((row) => {
      const matchesGroup = group === 'all' || getFileGroup(row) === group;
      const matchesSearch =
        !query ||
        row.title.toLocaleLowerCase().includes(query) ||
        row.taskTitle.toLocaleLowerCase().includes(query);
      return matchesGroup && matchesSearch;
    });
  }, [group, rows, search]);

  useEffect(() => {
    if (filteredRows.length === 0) {
      setSelectedKey(null);
      return;
    }
    setSelectedKey((current) =>
      filteredRows.some((row) => row.key === current) ? current : filteredRows[0].key,
    );
  }, [filteredRows]);

  const selected = useMemo(
    () => rows.find((row) => row.key === selectedKey) ?? null,
    [rows, selectedKey],
  );

  const downloadFile = async (row: Row) => {
    let blob: Blob;
    try {
      setWarning(null);
      blob = await getPicoArtifactContent(row.id, true);
    } catch (downloadError) {
      const detail = downloadError instanceof Error ? downloadError.message : String(downloadError);
      setWarning(
        `下载失败：${detail}。请用本页「下载文件」或 GET /api/pico/v1/artifacts/{id}/content?download=true（勿用虚构 /download 尾缀）。`,
      );
      return;
    }
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = row.title || 'artifact.txt';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <WorkbenchShell
      title="我的文件"
      subtitle="任务账本中的真实产物"
      backTo="/more"
      actions={
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-black/[0.08] px-2.5 text-[12px] text-[#555] hover:bg-black/[0.04] disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          刷新
        </button>
      }
    >
      <div className="flex h-full min-h-[420px] flex-col">
        <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-black/[0.06] bg-white px-3 py-2">
          <label className="relative min-w-[220px] flex-1" htmlFor="artifact-search">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#999]" />
            <input
              id="artifact-search"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="搜索文件名或来源任务"
              className="h-8 w-full rounded-md border border-black/[0.08] bg-[#f8f8f8] pl-8 pr-8 text-[12px] outline-none focus:border-black/20"
            />
            {search ? (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-[#999] hover:bg-black/[0.05]"
                aria-label="清除搜索"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </label>
          <select
            value={group}
            onChange={(event) => setGroup(event.target.value as FileGroup)}
            className="h-8 rounded-md border border-black/[0.08] bg-white px-2.5 text-[12px] text-[#555] outline-none"
            aria-label="文件类型"
          >
            {(Object.keys(GROUP_LABELS) as FileGroup[]).map((key) => (
              <option key={key} value={key}>
                {GROUP_LABELS[key]}
              </option>
            ))}
          </select>
          <span className="min-w-[64px] text-right text-[11px] text-[#999]">
            {filteredRows.length}/{rows.length} 个
          </span>
        </div>

        {error ? (
          <div
            role="alert"
            className="m-3 flex gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11.5px] text-red-800"
          >
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>
              文件加载失败：{error}
              <span className="mt-0.5 block opacity-80">请确认登录状态后重试。</span>
            </span>
          </div>
        ) : null}
        {warning ? (
          <div
            role="status"
            className="mx-3 mt-3 flex gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[11.5px] text-amber-900"
          >
            <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {warning}
          </div>
        ) : null}

        {loading && rows.length === 0 ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-[12px] text-[#8c8c8c]">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载文件
          </div>
        ) : rows.length === 0 && !error ? (
          <div className="flex flex-1 flex-col items-center justify-center gap-1.5 text-[color:var(--pico-ink-3)]">
            <div className="pico-icon-medallion mb-2 size-12">
              <PicoIcon name="folder-open" size="lg" />
            </div>
            <p className="text-[13px] font-medium text-[color:var(--pico-ink)]">暂无文件产物</p>
            <p className="max-w-xs text-center text-[11.5px] leading-4">
              任务产生可记录的文件后，会同时出现在这里和任务结果区
            </p>
            <button
              type="button"
              onClick={() => navigate('/c/new')}
              className="pico-cta-accent mt-3 px-4 py-2 text-[12px] font-medium"
            >
              新建任务生成文件
            </button>
          </div>
        ) : (
          <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(320px,42%)_minmax(0,1fr)]">
            <section className="min-h-0 overflow-y-auto border-r border-[color:var(--pico-line)] bg-[color:var(--pico-surface)]">
              {filteredRows.length === 0 ? (
                <div className="flex h-full min-h-48 flex-col items-center justify-center text-center">
                  <Search className="mb-2 h-6 w-6 text-[#bbb]" />
                  <p className="text-[12.5px] font-medium text-[#666]">没有匹配的文件</p>
                  <button
                    type="button"
                    onClick={() => {
                      setSearch('');
                      setGroup('all');
                    }}
                    className="mt-2 text-[11.5px] text-[#555] underline underline-offset-2"
                  >
                    清除筛选
                  </button>
                </div>
              ) : (
                <ul className="divide-y divide-black/[0.05]">
                  {filteredRows.map((row) => {
                    const rowGroup = getFileGroup(row);
                    const canOpen = typeof row.inline === 'string';
                    const isSelected = row.key === selectedKey;
                    return (
                      <li
                        key={row.key}
                        className={
                          isSelected
                            ? 'bg-[color:var(--pico-violet-wash)]'
                            : 'hover:bg-[color:var(--pico-surface-2)]'
                        }
                      >
                        <button
                          type="button"
                          onClick={() => setSelectedKey(row.key)}
                          className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left"
                        >
                          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]">
                            <FileTypeIcon group={rowGroup} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate text-[12.5px] font-medium text-[color:var(--pico-ink)]">
                              {row.title || '未命名文件'}
                            </span>
                            <span className="mt-0.5 block truncate text-[10.5px] text-[color:var(--pico-ink-2)]">
                              {getTypeLabel(row)} · {formatBytes(getInlineBytes(row.inline))} ·{' '}
                              {formatTime(row.taskCreatedAt)}
                            </span>
                            <span className="mt-0.5 block truncate text-[10.5px] text-[color:var(--pico-ink-3)]">
                              {row.taskTitle}
                            </span>
                          </span>
                          {canOpen ? (
                            <span className="inline-flex shrink-0 items-center gap-1 text-[10.5px] font-medium text-[#666]">
                              <Eye className="h-3 w-3" />
                              打开
                            </span>
                          ) : (
                            <span
                              className="shrink-0 text-[10px] text-[#aaa]"
                              title="账本未保存正文"
                            >
                              仅记录
                            </span>
                          )}
                        </button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>

            <section className="min-h-0 overflow-y-auto bg-[color:var(--pico-surface-2)]">
              {selected ? (
                <div className="flex min-h-full flex-col">
                  <div className="flex shrink-0 items-start gap-3 border-b border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 py-3">
                    <span className="pico-icon-medallion h-9 w-9 shrink-0">
                      <FileTypeIcon group={getFileGroup(selected)} />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="break-words text-[13px] font-semibold text-[color:var(--pico-ink)]">
                        {selected.title || '未命名文件'}
                      </h2>
                      <p className="mt-0.5 text-[10.5px] text-[#8c8c8c]">
                        {getTypeLabel(selected)} · {formatBytes(getInlineBytes(selected.inline))} ·{' '}
                        {formatTime(selected.taskCreatedAt)}
                      </p>
                      <p className="mt-0.5 truncate text-[10.5px] text-[#aaa]">
                        来源：{selected.taskTitle}
                      </p>
                    </div>
                    {typeof selected.inline === 'string' ? (
                      <button
                        type="button"
                        onClick={() => void downloadFile(selected)}
                        data-testid="files-hub-download-button"
                        className="pico-cta-accent inline-flex h-9 shrink-0 items-center gap-1.5 px-3 text-[12px] font-semibold"
                        title="下载到本地（/api/pico/v1/artifacts/{id}/content?download=true）"
                      >
                        <Download className="h-3.5 w-3.5" />
                        下载文件
                      </button>
                    ) : null}
                  </div>
                  {typeof selected.inline === 'string' ? (
                    <div className="min-h-0 flex-1 p-3">
                      <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-[#666]">
                        <Eye className="h-3.5 w-3.5" />
                        正文预览
                      </div>
                      <pre className="pico-panel max-h-[calc(100vh-190px)] overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11.5px] leading-[1.65] text-[color:var(--pico-ink)]">
                        {selected.inline ? selected.inline.slice(0, PREVIEW_LIMIT) : '（空文件）'}
                      </pre>
                      {selected.inline.length > PREVIEW_LIMIT ? (
                        <p className="mt-2 text-[10.5px] text-[#999]">
                          预览仅显示前 {PREVIEW_LIMIT.toLocaleString('zh-CN')}{' '}
                          个字符，下载保留完整正文。
                        </p>
                      ) : null}
                    </div>
                  ) : (
                    <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
                      <div className="pico-icon-medallion mb-2 size-12">
                        <PicoIcon name="doc" size="lg" />
                      </div>
                      <p className="text-[12.5px] font-medium text-[#666]">账本未保存文件正文</p>
                      <p className="mt-1 max-w-sm text-[11.5px] leading-4 text-[#999]">
                        当前数据只有文件记录，无法提供可靠预览或下载，因此未显示无效操作。
                      </p>
                    </div>
                  )}
                </div>
              ) : (
                <div className="flex h-full min-h-48 items-center justify-center text-[12px] text-[#999]">
                  从左侧选择文件查看详情
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </WorkbenchShell>
  );
}
