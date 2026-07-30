/**
 * S7 minimal human confirm — list proposed changes; confirm / reject.
 * No school business write; audit only.
 */
import { useCallback, useEffect, useState } from 'react';
import { Check, X, FileWarning, Loader2, Plus } from 'lucide-react';
import {
  confirmPicoChange,
  createPicoChange,
  listPicoChanges,
  rejectPicoChange,
  type PicoChange,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';

export default function ChangeConfirmBanner({
  taskId,
}: {
  taskId?: string | null;
}) {
  const [items, setItems] = useState<PicoChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const { changes } = await listPicoChanges();
      setItems((changes || []).filter((c) => c.status === 'proposed'));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    const id = window.setInterval(() => void refresh(), 8000);
    return () => window.clearInterval(id);
  }, [refresh, taskId]);

  const onConfirm = async (id: string) => {
    setBusyId(id);
    setError(null);
    try {
      await confirmPicoChange(id);
      setToast('已确认（仅审计，不写学校业务库）');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onReject = async (id: string) => {
    setBusyId(id);
    setError(null);
    try {
      await rejectPicoChange(id);
      setToast('已拒绝提案');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  const onDemoPropose = async () => {
    setBusyId('create');
    setError(null);
    try {
      await createPicoChange({
        title: '演示提案：更新班级备注',
        summary: 'S7 人确认路径演示。确认后只记审计，不会写入学校教务库。',
        payload: { demo: true, action: 'update_class_note', value: 'Pico 演示' },
        task_id: taskId || undefined,
      });
      setToast('已创建待确认提案');
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  };

  useEffect(() => {
    if (!toast) {
      return;
    }
    const t = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(t);
  }, [toast]);

  if (!items.length && !error && !toast) {
    return (
      <div className="flex items-center justify-between gap-2 border-b border-amber-100 bg-amber-50/80 px-3 py-1.5 text-[12px] text-amber-900">
        <span className="inline-flex items-center gap-1.5">
          <FileWarning className="h-3.5 w-3.5 opacity-70" />
          业务变更须人工确认 · 无静默写库
        </span>
        <button
          type="button"
          onClick={() => void onDemoPropose()}
          disabled={busyId === 'create'}
          className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-[11px] font-medium ring-1 ring-amber-200 hover:bg-amber-50 disabled:opacity-50"
        >
          {busyId === 'create' ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <Plus className="h-3 w-3" />
          )}
          新建演示提案
        </button>
      </div>
    );
  }

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-950">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <span className="inline-flex items-center gap-1.5 font-medium">
          <FileWarning className="h-3.5 w-3.5" />
          待确认变更（S7）
          {loading ? <Loader2 className="h-3 w-3 animate-spin opacity-60" /> : null}
        </span>
        <button
          type="button"
          onClick={() => void onDemoPropose()}
          disabled={busyId === 'create'}
          className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-[11px] ring-1 ring-amber-200"
        >
          <Plus className="h-3 w-3" />
          演示提案
        </button>
      </div>
      {error ? <p className="mb-1 text-[11px] text-red-700">{error}</p> : null}
      {toast ? <p className="mb-1 text-[11px] text-emerald-800">{toast}</p> : null}
      <ul className="space-y-2">
        {items.map((c) => (
          <li
            key={c.id}
            className="flex flex-wrap items-start justify-between gap-2 rounded-lg bg-white/90 px-2.5 py-2 ring-1 ring-amber-100"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium text-[#1a1a1a]">{c.title}</p>
              {c.summary ? (
                <p className="mt-0.5 line-clamp-2 text-[11.5px] text-[#6b6b6b]">{c.summary}</p>
              ) : null}
            </div>
            <div className="flex shrink-0 items-center gap-1">
              <button
                type="button"
                disabled={busyId === c.id}
                onClick={() => void onConfirm(c.id)}
                className={cn(
                  'inline-flex items-center gap-1 rounded-md bg-[#1a1a1a] px-2 py-1 text-[11px] font-medium text-white',
                  busyId === c.id && 'opacity-50',
                )}
              >
                <Check className="h-3 w-3" />
                确认
              </button>
              <button
                type="button"
                disabled={busyId === c.id}
                onClick={() => void onReject(c.id)}
                className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-red-700 ring-1 ring-red-200"
              >
                <X className="h-3 w-3" />
                拒绝
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
