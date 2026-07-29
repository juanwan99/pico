/**
 * Browser-side "workspace" picker — WorkBuddy-class task boundary.
 * Clean-room: local named spaces (not desktop folder ACL).
 * Selected workspace is injected into the next user message as context.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { FolderOpen, Check, Plus, ChevronDown, Trash2 } from 'lucide-react';
import { Button, TooltipAnchor } from '@librechat/client';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

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

/** Prefix for agent context when a non-default workspace is active */
export function workspaceContextPrefix(): string {
  const ws = getSelectedWorkspace();
  const bits: string[] = [];
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
  return bits.length ? bits.join(' ') + '\n' : '';
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
  const [selectedId, setSelectedId] = useState<string>(() =>
    typeof window !== 'undefined' ? localStorage.getItem(SELECTED_KEY) || 'default' : 'default',
  );

  useEffect(() => {
    setList(loadWorkspaces());
    setSelectedId(localStorage.getItem(SELECTED_KEY) || 'default');
  }, []);

  const selected = useMemo(
    () => list.find((w) => w.id === selectedId) ?? list[0],
    [list, selectedId],
  );
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((w) => w.name.toLowerCase().includes(q));
  }, [list, search]);

  const select = useCallback((id: string) => {
    setSelectedId(id);
    localStorage.setItem(SELECTED_KEY, id);
    setOpen(false);
  }, []);

  const addWorkspace = useCallback(() => {
    const name = window.prompt('为工作空间命名，本地将自动创建同名文件夹，命名后不可随意更改');
    if (!name?.trim()) {
      return;
    }
    const ws: PicoWorkspace = {
      id: `ws_${Date.now()}`,
      name: name.trim(),
    };
    setList((prev) => {
      const next = [...prev, ws];
      saveWorkspaces(next);
      return next;
    });
    select(ws.id);
  }, [localize, select]);

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

  const label = selected?.name || localize('com_ui_select_workspace');

  return (
    <div className="relative">
      <TooltipAnchor
        description={localize('com_ui_workspace_hint')}
        side="top"
        render={
          <Button
            type="button"
            size={compact ? 'icon' : 'sm'}
            variant="ghost"
            disabled={disabled}
            aria-label={localize('com_ui_select_workspace')}
            aria-expanded={open}
            data-testid="workspace-selector"
            className={cn(
              'h-8 gap-1.5 rounded-lg text-xs font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              !compact && 'px-2',
              open && 'bg-surface-hover text-text-primary',
            )}
            onClick={() => setOpen((v) => !v)}
          >
            <FolderOpen className="h-4 w-4 shrink-0" aria-hidden />
            {!compact && <span className="max-w-[7rem] truncate">{label}</span>}
            {!compact && <ChevronDown className="h-3 w-3 opacity-60" aria-hidden />}
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
          <div
            className="absolute bottom-full left-0 z-50 mb-2 w-64 overflow-hidden rounded-xl border border-border-light bg-white shadow-lg dark:bg-surface-secondary"
            role="listbox"
            aria-label={localize('com_ui_select_workspace')}
          >
            <div className="border-b border-border-light px-3 py-2">
              <p className="text-xs font-medium text-text-primary">
                {localize('com_ui_select_workspace')}
              </p>
              <p className="mt-0.5 text-[11px] leading-snug text-text-secondary">
                {localize('com_ui_workspace_hint')}
              </p>
            </div>
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
              {filtered.map((ws) => {
                const isSel = ws.id === selected?.id;
                return (
                  <li key={ws.id}>
                    <button
                      type="button"
                      role="option"
                      aria-selected={isSel}
                      className={cn(
                        'flex w-full items-start gap-2 px-3 py-2 text-left text-sm transition-colors hover:bg-surface-hover',
                        isSel && 'bg-surface-hover',
                      )}
                      onClick={() => select(ws.id)}
                    >
                      <FolderOpen className="mt-0.5 h-4 w-4 shrink-0 text-text-secondary" />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium text-text-primary">
                          {ws.name}
                        </span>
                        {ws.note ? (
                          <span className="mt-0.5 block truncate text-[11px] text-text-secondary">
                            {ws.note}
                          </span>
                        ) : null}
                      </span>
                      {isSel ? (
                        <Check className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                      ) : null}
                      {ws.id !== 'default' ? (
                        <button
                          type="button"
                          className="mt-0.5 rounded p-0.5 text-text-secondary hover:bg-red-50 hover:text-red-600"
                          aria-label="删除"
                          onClick={(e) => removeWorkspace(ws.id, e)}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      ) : null}
                    </button>
                  </li>
                );
              })}
            </ul>
            <div className="border-t border-border-light p-1.5 space-y-0.5">
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
