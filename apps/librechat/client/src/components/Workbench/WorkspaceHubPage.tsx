/**
 * Space hub backed by Pico workspaces and shared with the composer selector.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  Check,
  FolderKanban,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import {
  createPicoWorkspace,
  deletePicoWorkspace,
  listPicoWorkspaces,
  type PicoWorkspace,
} from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';

const WORKSPACES_KEY = 'pico:workspaces';
const SELECTED_KEY = 'pico:workspaceId';

type Notice = { tone: 'success' | 'error'; text: string } | null;

function readCachedWorkspaces(): PicoWorkspace[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(WORKSPACES_KEY) || '[]') as PicoWorkspace[];
    return Array.isArray(parsed)
      ? parsed.filter(
          (item) =>
            item &&
            typeof item.id === 'string' &&
            typeof item.name === 'string' &&
            item.id.length > 0 &&
            item.name.length > 0,
        )
      : [];
  } catch {
    return [];
  }
}

function writeCachedWorkspaces(workspaces: PicoWorkspace[]) {
  try {
    localStorage.setItem(WORKSPACES_KEY, JSON.stringify(workspaces));
  } catch {
    /* The API remains authoritative when browser storage is unavailable. */
  }
}

function readSelectedId() {
  try {
    return localStorage.getItem(SELECTED_KEY);
  } catch {
    return null;
  }
}

function writeSelectedId(id: string | null) {
  try {
    if (id) {
      localStorage.setItem(SELECTED_KEY, id);
    } else {
      localStorage.removeItem(SELECTED_KEY);
    }
  } catch {
    /* Selection still works for the current render. */
  }
}

function workspaceKindLabel(kind?: string) {
  return kind === 'managed' ? '托管空间' : kind || '工作空间';
}

function formatCreatedAt(value?: string | null) {
  if (!value) {
    return '创建时间未知';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '创建时间未知';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export default function WorkspaceHubPage() {
  const navigate = useNavigate();
  const [list, setList] = useState<PicoWorkspace[]>(() =>
    typeof window === 'undefined' ? [] : readCachedWorkspaces(),
  );
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    typeof window === 'undefined' ? null : readSelectedId(),
  );
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice>(null);

  const selected = useMemo(
    () => list.find((workspace) => workspace.id === selectedId) ?? null,
    [list, selectedId],
  );

  const applyList = useCallback(
    (workspaces: PicoWorkspace[], preferredId: string | null) => {
      setList(workspaces);
      writeCachedWorkspaces(workspaces);
      const nextSelectedId = workspaces.some((workspace) => workspace.id === preferredId)
        ? preferredId
        : (workspaces[0]?.id ?? null);
      setSelectedId(nextSelectedId);
      writeSelectedId(nextSelectedId);
    },
    [],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setNotice(null);
    try {
      const { workspaces } = await listPicoWorkspaces();
      applyList(workspaces || [], readSelectedId());
    } catch (error) {
      setNotice({
        tone: 'error',
        text:
          error instanceof Error
            ? `空间同步失败：${error.message}`
            : `空间同步失败：${String(error)}`,
      });
    } finally {
      setLoading(false);
    }
  }, [applyList]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selectWorkspace = (workspace: PicoWorkspace) => {
    setSelectedId(workspace.id);
    writeSelectedId(workspace.id);
    setNotice({ tone: 'success', text: `已切换到「${workspace.name}」` });
  };

  const onCreate = async () => {
    const trimmedName = name.trim();
    if (!trimmedName || creating) {
      return;
    }
    if (list.some((workspace) => workspace.name.trim() === trimmedName)) {
      setNotice({ tone: 'error', text: '已有同名空间，请换一个名称' });
      return;
    }
    setCreating(true);
    setNotice(null);
    try {
      const { workspace } = await createPicoWorkspace(trimmedName, '浏览器工作空间');
      applyList([...list, workspace], workspace.id);
      setName('');
      setNotice({ tone: 'success', text: `空间「${workspace.name}」已创建并设为当前空间` });
    } catch (error) {
      setNotice({
        tone: 'error',
        text: error instanceof Error ? `创建失败：${error.message}` : `创建失败：${String(error)}`,
      });
    } finally {
      setCreating(false);
    }
  };

  const onDelete = async (workspace: PicoWorkspace) => {
    if (deletingId) {
      return;
    }
    setDeletingId(workspace.id);
    setNotice(null);
    try {
      await deletePicoWorkspace(workspace.id);
      const nextList = list.filter((item) => item.id !== workspace.id);
      applyList(nextList, selectedId === workspace.id ? null : selectedId);
      setConfirmingId(null);
      setNotice({ tone: 'success', text: `空间「${workspace.name}」已删除` });
    } catch (error) {
      setNotice({
        tone: 'error',
        text: error instanceof Error ? `删除失败：${error.message}` : `删除失败：${String(error)}`,
      });
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <WorkbenchShell
      title="空间"
      subtitle="管理任务、附件与产物的工作边界"
      actions={
        <>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-black/[0.08] text-[#666] hover:bg-black/[0.04] disabled:opacity-50"
            aria-label="刷新空间"
            title="刷新空间"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="h-8 rounded-lg border border-black/[0.08] px-2.5 text-[12px] text-[#3d3d3d] hover:bg-black/[0.04]"
          >
            项目
          </button>
        </>
      }
    >
      <div className="mx-auto grid w-full max-w-5xl gap-3 p-4 lg:grid-cols-[minmax(0,1fr)_280px]">
        <section className="min-w-0 overflow-hidden rounded-lg border border-black/[0.06] bg-white">
          <div className="flex h-11 items-center justify-between border-b border-black/[0.06] px-3">
            <div>
              <h2 className="text-[13px] font-semibold text-[#1f1f1f]">全部空间</h2>
              <p className="text-[11px] text-[#8c8c8c]">{loading ? '正在同步' : `共 ${list.length} 个`}</p>
            </div>
          </div>

          {loading && list.length === 0 ? (
            <div className="flex items-center justify-center gap-2 py-16 text-[12px] text-[#8c8c8c]">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载空间
            </div>
          ) : list.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FolderKanban className="mb-2 h-8 w-8 text-[#c5c5c5]" strokeWidth={1.25} />
              <p className="text-[13px] font-medium text-[#555]">暂无空间</p>
              <p className="mt-1 text-[11.5px] text-[#999]">在右侧创建第一个托管空间</p>
            </div>
          ) : (
            <ul className="divide-y divide-black/[0.05]">
              {list.map((workspace) => {
                const isSelected = workspace.id === selectedId;
                const isConfirming = workspace.id === confirmingId;
                const isDeleting = workspace.id === deletingId;
                return (
                  <li key={workspace.id} className={isSelected ? 'bg-[#f7f7f7]' : ''}>
                    <div className="flex min-h-[60px] items-center gap-3 px-3 py-2">
                      <button
                        type="button"
                        onClick={() => selectWorkspace(workspace)}
                        className="flex min-w-0 flex-1 items-center gap-3 text-left"
                        aria-pressed={isSelected}
                      >
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-md bg-[#edf1f4] text-[#4b5560]">
                          <FolderKanban className="h-4 w-4" />
                        </span>
                        <span className="min-w-0 flex-1">
                          <span className="flex items-center gap-2">
                            <span className="truncate text-[13px] font-medium text-[#222]">
                              {workspace.name}
                            </span>
                            {isSelected ? (
                              <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-[#1f1f1f] px-2 py-0.5 text-[10px] font-medium text-white">
                                <Check className="h-2.5 w-2.5" />
                                当前
                              </span>
                            ) : null}
                          </span>
                          <span className="mt-0.5 block truncate text-[11px] text-[#8c8c8c]">
                            {workspace.note || workspaceKindLabel(workspace.kind)} ·{' '}
                            {formatCreatedAt(workspace.created_at)}
                          </span>
                        </span>
                      </button>
                      <button
                        type="button"
                        className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-[#999] hover:bg-red-50 hover:text-red-600"
                        aria-label={`删除空间 ${workspace.name}`}
                        title="删除空间"
                        onClick={() => setConfirmingId(isConfirming ? null : workspace.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {isConfirming ? (
                      <div className="flex items-center justify-between gap-3 border-t border-red-100 bg-red-50/70 px-3 py-2">
                        <p className="min-w-0 text-[11.5px] text-red-800">
                          删除后无法恢复。确认删除「{workspace.name}」？
                        </p>
                        <div className="flex shrink-0 gap-1.5">
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => setConfirmingId(null)}
                            className="h-7 rounded-md border border-black/[0.08] bg-white px-2.5 text-[11px]"
                          >
                            取消
                          </button>
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => void onDelete(workspace)}
                            className="inline-flex h-7 items-center gap-1 rounded-md bg-red-600 px-2.5 text-[11px] font-medium text-white disabled:opacity-60"
                          >
                            {isDeleting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                            确认删除
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <aside className="space-y-3">
          <section className="rounded-lg border border-black/[0.06] bg-white p-3">
            <h2 className="text-[13px] font-semibold text-[#1f1f1f]">新建空间</h2>
            <p className="mt-0.5 text-[11px] leading-4 text-[#8c8c8c]">
              新空间会自动设为当前任务空间
            </p>
            <label className="mt-3 block text-[11px] font-medium text-[#666]" htmlFor="workspace-name">
              空间名称
            </label>
            <input
              id="workspace-name"
              value={name}
              maxLength={80}
              onChange={(event) => setName(event.target.value)}
              placeholder="例如：教学教研"
              className="mt-1 h-9 w-full rounded-md border border-black/[0.1] bg-[#fafafa] px-2.5 text-[12.5px] outline-none focus:border-black/30"
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  void onCreate();
                }
              }}
            />
            <div className="mt-1 text-right text-[10px] text-[#aaa]">{name.length}/80</div>
            <button
              type="button"
              disabled={!name.trim() || creating}
              onClick={() => void onCreate()}
              className="mt-2 inline-flex h-8 w-full items-center justify-center gap-1.5 rounded-md bg-[#1f1f1f] text-[12px] font-medium text-white hover:bg-black disabled:opacity-40"
            >
              {creating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
              {creating ? '创建中' : '创建空间'}
            </button>
          </section>

          <section className="rounded-lg border border-black/[0.06] bg-white p-3">
            <p className="text-[11px] font-medium text-[#777]">当前空间</p>
            {selected ? (
              <>
                <p className="mt-1 truncate text-[13px] font-semibold text-[#222]">{selected.name}</p>
                <p className="mt-1 text-[11px] leading-4 text-[#888]">
                  {selected.note || '任务将在此空间边界内运行'}
                </p>
              </>
            ) : (
              <p className="mt-1 text-[11.5px] text-[#999]">尚未选择空间</p>
            )}
          </section>

          {notice ? (
            <div
              role={notice.tone === 'error' ? 'alert' : 'status'}
              className={`flex gap-2 rounded-lg border px-3 py-2 text-[11.5px] leading-4 ${
                notice.tone === 'error'
                  ? 'border-red-200 bg-red-50 text-red-800'
                  : 'border-emerald-200 bg-emerald-50 text-emerald-800'
              }`}
            >
              {notice.tone === 'error' ? (
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              ) : (
                <Check className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              )}
              <span className="break-words">{notice.text}</span>
            </div>
          ) : null}
        </aside>
      </div>
    </WorkbenchShell>
  );
}
