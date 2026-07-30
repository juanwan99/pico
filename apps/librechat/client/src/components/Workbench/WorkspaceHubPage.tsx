/**
 * 空间 — Pico workspaces list/create (WorkBuddy space rail).
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FolderKanban, Loader2, Plus, Trash2 } from 'lucide-react';
import {
  createPicoWorkspace,
  deletePicoWorkspace,
  listPicoWorkspaces,
  type PicoWorkspace,
} from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';

export default function WorkspaceHubPage() {
  const navigate = useNavigate();
  const [list, setList] = useState<PicoWorkspace[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState('');
  const [creating, setCreating] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { workspaces } = await listPicoWorkspaces();
      setList(workspaces || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setList([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const onCreate = async () => {
    if (!name.trim() || creating) {
      return;
    }
    setCreating(true);
    setError(null);
    try {
      await createPicoWorkspace(name.trim(), '浏览器工作空间');
      setName('');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <WorkbenchShell
      title="空间"
      subtitle="任务文件边界 · 浏览器版"
      actions={
        <button
          type="button"
          onClick={() => navigate('/projects')}
          className="rounded-lg border border-black/[0.08] px-2.5 py-1.5 text-[12px]"
        >
          项目
        </button>
      }
    >
      <div className="mx-auto w-full max-w-xl space-y-4 p-5">
        <div className="rounded-2xl border border-black/[0.06] bg-white p-4">
          <p className="mb-2 text-[12px] font-medium text-[#8c8c8c]">新建空间</p>
          <div className="flex gap-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：默认工作空间"
              className="min-w-0 flex-1 rounded-xl border border-black/[0.08] px-3 py-2 text-[13px] outline-none focus:border-black/20"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  void onCreate();
                }
              }}
            />
            <button
              type="button"
              disabled={!name.trim() || creating}
              onClick={() => void onCreate()}
              className="inline-flex items-center gap-1 rounded-xl bg-[#1a1a1a] px-3 py-2 text-[12.5px] font-medium text-white disabled:opacity-40"
            >
              <Plus className="h-3.5 w-3.5" />
              创建
            </button>
          </div>
        </div>

        {error ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">
            {error}
          </div>
        ) : null}

        {loading ? (
          <div className="flex justify-center gap-2 py-12 text-[#8c8c8c]">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载空间…
          </div>
        ) : list.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-black/[0.08] bg-white py-12 text-center text-[13px] text-[#9a9a9a]">
            暂无空间 · 创建一个作为任务上下文边界
          </div>
        ) : (
          <ul className="space-y-2">
            {list.map((w) => (
              <li
                key={w.id}
                className="flex items-center gap-3 rounded-xl border border-black/[0.06] bg-white px-3 py-3"
              >
                <div className="flex size-9 items-center justify-center rounded-lg bg-[#edf1f4]">
                  <FolderKanban className="h-4 w-4" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13.5px] font-medium">{w.name}</p>
                  <p className="text-[11px] text-[#8c8c8c]">{w.kind || 'managed'}</p>
                </div>
                <button
                  type="button"
                  className="rounded-lg p-2 text-[#9a9a9a] hover:bg-black/[0.04] hover:text-red-600"
                  aria-label="删除空间"
                  onClick={() => {
                    if (window.confirm(`删除空间「${w.name}」？`)) {
                      void deletePicoWorkspace(w.id).then(refresh).catch((e) => {
                        setError(e instanceof Error ? e.message : String(e));
                      });
                    }
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </WorkbenchShell>
  );
}
