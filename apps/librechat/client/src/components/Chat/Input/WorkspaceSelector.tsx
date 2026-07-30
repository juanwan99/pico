/**
 * Workspace picker backed by Pico /v1/workspaces.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  Check,
  ChevronDown,
  FolderOpen,
  Loader2,
  Plus,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { Button, TooltipAnchor } from '@librechat/client';
import {
  createPicoWorkspace,
  deletePicoWorkspace,
  listPicoWorkspaces,
  type PicoWorkspace,
} from '~/data-provider/pico/api';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

const STORAGE_KEY = 'pico:workspaces';
const SELECTED_KEY = 'pico:workspaceId';

function loadWorkspaces(): PicoWorkspace[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') as PicoWorkspace[];
    return Array.isArray(parsed)
      ? parsed.filter(
          (workspace) =>
            workspace &&
            typeof workspace.id === 'string' &&
            workspace.id.length > 0 &&
            typeof workspace.name === 'string' &&
            workspace.name.length > 0,
        )
      : [];
  } catch {
    return [];
  }
}

function saveWorkspaces(list: PicoWorkspace[]) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
  } catch {
    /* The API remains authoritative when browser storage is unavailable. */
  }
}

function loadSelectedId() {
  try {
    return localStorage.getItem(SELECTED_KEY);
  } catch {
    return null;
  }
}

function saveSelectedId(id: string | null) {
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

function errorMessage(prefix: string, error: unknown) {
  return error instanceof Error ? `${prefix}：${error.message}` : `${prefix}：${String(error)}`;
}

export function getSelectedWorkspace(): PicoWorkspace | null {
  const list = loadWorkspaces();
  const id = loadSelectedId();
  return list.find((workspace) => workspace.id === id) ?? list[0] ?? null;
}

/** Prefix for agent context - includes Pico-Convo for ledger mapping. */
export function workspaceContextPrefix(conversationId?: string | null): string {
  const ws = getSelectedWorkspace();
  const bits: string[] = [];
  if (conversationId && conversationId !== 'new') {
    bits.push(`【Pico-Convo:${conversationId}】`);
  }
  if (ws) {
    bits.push(`【工作空间：${ws.name}】${ws.note ? `（${ws.note}）` : ''}`);
  }
  try {
    const perm = localStorage.getItem('pico:permissionMode') || 'default';
    bits.push(perm === 'full' ? '【权限：完全访问】' : '【权限：默认沙箱】');
    const model = localStorage.getItem('pico:modelMode');
    if (model && model !== 'Auto') {
      bits.push(`【模型偏好：${model}】`);
    }
  } catch {
    /* ignore */
  }
  return bits.length ? `${bits.join(' ')}\n` : '';
}

export default function WorkspaceSelector({
  disabled = false,
  compact = false,
}: {
  disabled?: boolean;
  compact?: boolean;
}) {
  const localize = useLocalize();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [list, setList] = useState<PicoWorkspace[]>(() =>
    typeof window !== 'undefined' ? loadWorkspaces() : [],
  );
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    typeof window !== 'undefined' ? loadSelectedId() : null,
  );
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const applyList = useCallback((workspaces: PicoWorkspace[], preferredId: string | null) => {
    const next = workspaces || [];
    const nextSelectedId = next.some((workspace) => workspace.id === preferredId)
      ? preferredId
      : (next[0]?.id ?? null);
    setList(next);
    saveWorkspaces(next);
    setSelectedId(nextSelectedId);
    saveSelectedId(nextSelectedId);
  }, []);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { workspaces } = await listPicoWorkspaces();
      applyList(workspaces || [], loadSelectedId());
    } catch (refreshError) {
      setError(errorMessage('空间同步失败', refreshError));
    } finally {
      setLoading(false);
    }
  }, [applyList]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const selected = useMemo(
    () => list.find((workspace) => workspace.id === selectedId) ?? null,
    [list, selectedId],
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return list;
    }
    return list.filter((workspace) => workspace.name.toLowerCase().includes(q));
  }, [list, search]);

  const select = useCallback((id: string) => {
    setSelectedId(id);
    saveSelectedId(id);
    setOpen(false);
  }, []);

  const addWorkspace = useCallback(() => {
    const name = window.prompt('为工作空间命名（托管边界；浏览器不创建本机文件夹）');
    const trimmedName = name?.trim();
    if (!trimmedName || creating) {
      return;
    }
    if (list.some((workspace) => workspace.name.trim() === trimmedName)) {
      setError('已有同名空间，请换一个名称');
      return;
    }
    void (async () => {
      setCreating(true);
      setError(null);
      try {
        const { workspace } = await createPicoWorkspace(trimmedName, '浏览器工作空间');
        setList((previous) => {
          const next = [...previous, workspace];
          saveWorkspaces(next);
          return next;
        });
        setSelectedId(workspace.id);
        saveSelectedId(workspace.id);
        setOpen(false);
      } catch (createError) {
        setError(errorMessage('创建失败', createError));
      } finally {
        setCreating(false);
      }
    })();
  }, [creating, list]);

  const removeWorkspace = useCallback(
    async (workspace: PicoWorkspace) => {
      if (deletingId) {
        return;
      }
      setDeletingId(workspace.id);
      setError(null);
      try {
        await deletePicoWorkspace(workspace.id);
        setList((previous) => {
          const next = previous.filter((item) => item.id !== workspace.id);
          saveWorkspaces(next);
          if (selectedId === workspace.id) {
            const nextSelectedId = next[0]?.id ?? null;
            setSelectedId(nextSelectedId);
            saveSelectedId(nextSelectedId);
          }
          return next;
        });
        setConfirmingId(null);
      } catch (deleteError) {
        setError(errorMessage('删除失败', deleteError));
      } finally {
        setDeletingId(null);
      }
    },
    [deletingId, selectedId],
  );

  return (
    <div className="relative">
      <TooltipAnchor
        description={localize('com_ui_workspace') || '工作空间'}
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={disabled}
            className={cn(
              'h-8 gap-1.5 rounded-lg px-2 text-[12.5px] font-medium text-[#6b6b6b] hover:bg-black/[0.04]',
              compact && 'px-1.5',
            )}
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            <FolderOpen className="h-3.5 w-3.5" />
            {!compact && (
              <span className="max-w-[7rem] truncate">
                {selected?.name || (loading ? '同步工作空间' : '选择工作空间')}
              </span>
            )}
            <ChevronDown className="h-3.5 w-3.5 opacity-60" />
          </Button>
        }
      />
      {open && (
        <>
          <button
            type="button"
            className="fixed inset-0 z-40 cursor-default"
            aria-label="close"
            onClick={() => setOpen(false)}
          />
          <div className="absolute bottom-full left-0 z-50 mb-2 w-64 overflow-hidden rounded-lg border border-black/[0.08] bg-white shadow-lg dark:border-border-light dark:bg-surface-secondary">
            <div className="flex items-center gap-1.5 border-b border-border-light px-2 py-2">
              <input
                className="min-w-0 flex-1 rounded-lg border border-black/[0.08] bg-[#fafafa] px-2.5 py-1.5 text-xs outline-none"
                placeholder="搜索工作空间"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
              />
              <button
                type="button"
                onClick={() => void refresh()}
                disabled={loading}
                className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[#777] hover:bg-black/[0.05] disabled:opacity-50"
                aria-label="刷新工作空间"
                title="刷新工作空间"
              >
                <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
              </button>
            </div>
            {error ? (
              <div role="alert" className="flex gap-1.5 border-b border-red-100 bg-red-50 px-3 py-2 text-[11px] leading-4 text-red-700">
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span className="min-w-0 break-words">{error}</span>
              </div>
            ) : null}
            <ul className="max-h-56 overflow-y-auto py-1">
              {loading && list.length === 0 ? (
                <li className="flex items-center justify-center gap-1.5 px-3 py-4 text-xs text-text-secondary">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  正在同步空间
                </li>
              ) : null}
              {!loading && filtered.length === 0 ? (
                <li className="px-3 py-3 text-center text-xs text-text-secondary">
                  {search ? '未找到工作空间' : '暂无工作空间'}
                </li>
              ) : null}
              {filtered.map((workspace) => {
                const isConfirming = workspace.id === confirmingId;
                const isDeleting = workspace.id === deletingId;
                return (
                  <li key={workspace.id}>
                    <div className="flex items-center gap-1 px-1">
                      <button
                        type="button"
                        className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-2 py-2 text-left text-[13px] hover:bg-[#f5f5f5]"
                        onClick={() => select(workspace.id)}
                      >
                        <span className="min-w-0 flex-1">
                          <span className="block truncate font-medium">{workspace.name}</span>
                          {workspace.note ? (
                            <span className="block truncate text-[11px] text-[#9a9a9a]">
                              {workspace.note}
                            </span>
                          ) : null}
                        </span>
                        {selectedId === workspace.id ? (
                          <Check className="h-3.5 w-3.5 shrink-0" />
                        ) : null}
                      </button>
                      <button
                        type="button"
                        className={cn(
                          'inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md text-[#aaa] hover:bg-red-50 hover:text-red-600',
                          isConfirming && 'bg-red-50 text-red-600',
                        )}
                        onClick={() => setConfirmingId(isConfirming ? null : workspace.id)}
                        aria-label={`删除工作空间 ${workspace.name}`}
                        title="删除工作空间"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                    {isConfirming ? (
                      <div className="mx-1 mb-1 flex items-center justify-between gap-2 rounded-md bg-red-50 px-2 py-1.5">
                        <span className="min-w-0 truncate text-[10.5px] text-red-700">确认删除？</span>
                        <div className="flex shrink-0 gap-1">
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => setConfirmingId(null)}
                            className="h-6 rounded border border-red-100 bg-white px-2 text-[10.5px] text-[#666]"
                          >
                            取消
                          </button>
                          <button
                            type="button"
                            disabled={isDeleting}
                            onClick={() => void removeWorkspace(workspace)}
                            className="inline-flex h-6 items-center gap-1 rounded bg-red-600 px-2 text-[10.5px] text-white disabled:opacity-60"
                          >
                            {isDeleting ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
                            删除
                          </button>
                        </div>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
            <div className="space-y-0.5 border-t border-border-light p-1.5">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary disabled:opacity-50"
                onClick={addWorkspace}
                disabled={creating}
              >
                {creating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Plus className="h-3.5 w-3.5" />
                )}
                {creating ? '创建中' : '新建工作空间'}
              </button>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-text-secondary opacity-60"
                title="浏览器版后置：本地全盘目录"
                disabled
              >
                <FolderOpen className="h-3.5 w-3.5" />
                打开本地文件夹（桌面能力后置）
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
