/**
 * Workspace picker — syncs with Pico /v1/workspaces when proxy available.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { FolderOpen, Check, Plus, ChevronDown, Trash2 } from 'lucide-react';
import { Button, TooltipAnchor } from '@librechat/client';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';
import { createPicoWorkspace, listPicoWorkspaces } from '~/data-provider/pico/api';

const STORAGE_KEY = 'pico:workspaces';
const SELECTED_KEY = 'pico:workspaceId';

export type PicoWorkspace = {
  id: string;
  name: string;
  note?: string;
};

function loadWorkspaces(): PicoWorkspace[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as PicoWorkspace[];
      if (Array.isArray(parsed) && parsed.length) {
        return parsed;
      }
    }
  } catch {
    /* ignore */
  }
  return [
    { id: 'default', name: '默认工作空间', note: '浏览器会话产物与附件边界' },
    { id: 'teach', name: '教学教研', note: '教案、课件、学情相关任务' },
    { id: 'office', name: '日常办公', note: '纪要、文档、汇报' },
  ];
}

function saveWorkspaces(list: PicoWorkspace[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(list));
}

export function getSelectedWorkspace(): PicoWorkspace | null {
  const list = loadWorkspaces();
  const id = localStorage.getItem(SELECTED_KEY) || 'default';
  return list.find((w) => w.id === id) ?? list[0] ?? null;
}

/** Prefix for agent context — includes Pico-Convo for ledger mapping */
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
  const [selectedId, setSelectedId] = useState(
    () => (typeof window !== 'undefined' && localStorage.getItem(SELECTED_KEY)) || 'default',
  );

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { workspaces } = await listPicoWorkspaces();
        if (!alive || !workspaces?.length) {
          return;
        }
        setList((prev) => {
          const map = new Map(prev.map((w) => [w.id, w]));
          for (const w of workspaces) {
            map.set(w.id, { id: w.id, name: w.name, note: w.note || '托管工作空间' });
          }
          const next = Array.from(map.values());
          saveWorkspaces(next);
          return next;
        });
      } catch {
        /* proxy may be down */
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const selected = useMemo(
    () => list.find((w) => w.id === selectedId) ?? list[0],
    [list, selectedId],
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return list;
    }
    return list.filter((w) => w.name.toLowerCase().includes(q));
  }, [list, search]);

  const select = useCallback((id: string) => {
    setSelectedId(id);
    localStorage.setItem(SELECTED_KEY, id);
    setOpen(false);
  }, []);

  const addWorkspace = useCallback(() => {
    const name = window.prompt('为工作空间命名（托管边界；浏览器不创建本机文件夹）');
    if (!name?.trim()) {
      return;
    }
    void (async () => {
      let ws: PicoWorkspace = {
        id: `ws_${Date.now()}`,
        name: name.trim(),
        note: '托管工作空间',
      };
      try {
        const { workspace } = await createPicoWorkspace(name.trim());
        ws = { id: workspace.id, name: workspace.name, note: workspace.note || '托管工作空间' };
      } catch {
        /* local fallback */
      }
      setList((prev) => {
        const next = [...prev, ws];
        saveWorkspaces(next);
        return next;
      });
      select(ws.id);
    })();
  }, [select]);

  const removeWorkspace = useCallback(
    (id: string, e: React.MouseEvent) => {
      e.stopPropagation();
      if (id === 'default') {
        return;
      }
      setList((prev) => {
        const next = prev.filter((w) => w.id !== id);
        saveWorkspaces(next);
        return next;
      });
      if (selectedId === id) {
        select('default');
      }
    },
    [selectedId, select],
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
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
          >
            <FolderOpen className="h-3.5 w-3.5" />
            {!compact && <span className="max-w-[7rem] truncate">{selected?.name || '选择工作空间'}</span>}
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
          <div className="absolute bottom-full left-0 z-50 mb-2 w-64 overflow-hidden rounded-xl border border-black/[0.08] bg-white shadow-lg dark:border-border-light dark:bg-surface-secondary">
            <div className="border-b border-border-light px-3 py-2">
              <input
                className="w-full rounded-lg border border-black/[0.08] bg-[#fafafa] px-2.5 py-1.5 text-xs outline-none"
                placeholder="搜索工作空间"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
            <ul className="max-h-56 overflow-y-auto py-1">
              {filtered.length === 0 ? (
                <li className="px-3 py-3 text-center text-xs text-text-secondary">未找到工作空间</li>
              ) : null}
              {filtered.map((ws) => (
                <li key={ws.id}>
                  <button
                    type="button"
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-[13px] hover:bg-[#f5f5f5]"
                    onClick={() => select(ws.id)}
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{ws.name}</span>
                      {ws.note ? (
                        <span className="block truncate text-[11px] text-[#9a9a9a]">{ws.note}</span>
                      ) : null}
                    </span>
                    {selectedId === ws.id ? <Check className="h-3.5 w-3.5 shrink-0" /> : null}
                    {ws.id !== 'default' ? (
                      <span
                        role="button"
                        tabIndex={0}
                        className="rounded p-1 text-[#b0b0b0] hover:bg-black/[0.05] hover:text-red-500"
                        onClick={(e) => removeWorkspace(ws.id, e)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
            <div className="space-y-0.5 border-t border-border-light p-1.5">
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary"
                onClick={addWorkspace}
              >
                <Plus className="h-3.5 w-3.5" />
                新建工作空间
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
