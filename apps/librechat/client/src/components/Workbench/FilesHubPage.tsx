/**
 * 我的文件 — global artifact ledger view (WorkBuddy「资料库」轻量版).
 * Pulls Task → artifacts from Pico API via LibreChat /api/pico.
 */
import { useCallback, useEffect, useState } from 'react';
import { FileText, Loader2, RefreshCw } from 'lucide-react';
import { getPicoTask, listPicoTasks, type PicoArtifact } from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';
import { cn } from '~/utils';

type Row = PicoArtifact & { taskId: string; taskTitle: string };

export default function FilesHubPage() {
  const [rows, setRows] = useState<Row[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [openId, setOpenId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { tasks } = await listPicoTasks();
      const list = tasks || [];
      const out: Row[] = [];
      for (const t of list.slice(0, 30)) {
        try {
          const detail = await getPicoTask(t.id);
          for (const a of detail.artifacts || []) {
            if (a.kind === 'doc' && a.title === '回复摘要') {
              continue;
            }
            out.push({
              ...a,
              taskId: t.id,
              taskTitle: t.title || '未命名任务',
            });
          }
        } catch {
          /* skip task */
        }
      }
      setRows(out);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const openBody = rows.find((r) => r.id === openId);

  return (
    <WorkbenchShell
      title="我的文件"
      subtitle="来自任务账本的产物"
      backTo="/more"
      actions={
        <button
          type="button"
          onClick={() => void refresh()}
          className="inline-flex h-8 items-center gap-1 rounded-lg border border-black/[0.08] px-2.5 text-[12px]"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          刷新
        </button>
      }
    >
      <div className="mx-auto w-full max-w-3xl p-4">
        {error ? (
          <div className="mb-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-900">
            {error}
            <span className="mt-1 block text-[11px] opacity-80">
              若未登录或账本不可用，请先完成一次真聊再回来。
            </span>
          </div>
        ) : null}

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-16 text-[#8c8c8c]">
            <Loader2 className="h-4 w-4 animate-spin" />
            加载产物…
          </div>
        ) : rows.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-2xl border border-dashed border-black/[0.08] bg-white py-16 text-[#9a9a9a]">
            <FileText className="h-9 w-9 opacity-35" strokeWidth={1.25} />
            <p className="text-[13px] font-medium text-[#6b6b6b]">暂无文件产物</p>
            <p className="max-w-xs text-center text-[12px] leading-relaxed">
              在任务中让模型创建文件（如 hello.txt）后，会出现在这里与会话右栏结果区
            </p>
          </div>
        ) : (
          <ul className="space-y-2">
            {rows.map((r) => (
              <li key={r.id}>
                <button
                  type="button"
                  onClick={() => setOpenId(r.id === openId ? null : r.id)}
                  className="flex w-full items-center gap-3 rounded-xl border border-black/[0.06] bg-white px-3 py-3 text-left shadow-sm hover:border-black/10"
                >
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[#e8f1ff] text-[10px] font-bold text-[#3b6fd9]">
                    {r.title?.toLowerCase().endsWith('.txt') ? 'TXT' : 'FILE'}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13.5px] font-medium text-[#1a1a1a]">{r.title}</p>
                    <p className="truncate text-[11.5px] text-[#8c8c8c]">{r.taskTitle}</p>
                  </div>
                  <span className="text-[11px] text-[#9a9a9a]">{r.kind}</span>
                </button>
                {openId === r.id && openBody ? (
                  <pre className="mt-1 max-h-48 overflow-auto rounded-xl bg-[#f5f5f5] p-3 text-[12px] leading-relaxed text-[#3d3d3d]">
                    {(openBody.inline || '（无正文）').slice(0, 8000)}
                  </pre>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </WorkbenchShell>
  );
}
