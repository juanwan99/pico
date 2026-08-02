/**
 * S7 human confirmation — show task-scoped changes and make terminal state explicit.
 * No school business write; audit only.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Check, FileWarning, Loader2, X } from 'lucide-react';
import {
  confirmPicoChange,
  listPicoChanges,
  rejectPicoChange,
  type PicoChange,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';

const STATUS_LABEL: Record<PicoChange['status'], string> = {
  proposed: '待确认',
  confirmed: '已确认',
  rejected: '已拒绝',
};

const STATUS_CLASS: Record<PicoChange['status'], string> = {
  proposed: 'bg-amber-100 text-amber-800',
  confirmed: 'bg-emerald-50 text-emerald-700',
  rejected: 'bg-red-50 text-red-700',
};

const CONFIRM_LABEL = '确认';
const REJECT_LABEL = '拒绝';

function safeChangeError(action: '读取' | '确认' | '拒绝', error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes('401')) {
    return `${action}变更失败：登录已失效，请刷新页面后重新登录`;
  }
  if (message.includes('403')) {
    return `${action}变更失败：当前账号没有操作权限`;
  }
  if (message.includes('404')) {
    return `${action}变更失败：变更不存在或无权限`;
  }
  if (message.includes('400') || message.includes('409') || message.includes('cannot transition')) {
    return `${action}变更失败：状态已更新，请核对最新结果`;
  }
  if (message.includes('502') || message.includes('unavailable')) {
    return `${action}变更失败：变更服务暂时不可用，请稍后重试`;
  }
  return `${action}变更失败，请稍后重试`;
}

type ChangeConfirmBannerProps = {
  taskId?: string | null;
  onChanged?: () => void | Promise<void>;
};

export default function ChangeConfirmBanner({ taskId, onChanged }: ChangeConfirmBannerProps) {
  const [items, setItems] = useState<PicoChange[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const requestVersion = useRef(0);
  const currentTaskId = useRef(taskId);
  currentTaskId.current = taskId;

  const refresh = useCallback(async () => {
    const requestedTaskId = taskId;
    const version = ++requestVersion.current;
    if (!requestedTaskId) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const { changes } = await listPicoChanges({ taskId: requestedTaskId });
      if (version !== requestVersion.current || currentTaskId.current !== requestedTaskId) {
        return;
      }
      setItems((changes || []).filter((item) => item.task_id === requestedTaskId));
    } catch (refreshError) {
      if (version !== requestVersion.current || currentTaskId.current !== requestedTaskId) {
        return;
      }
      setError(safeChangeError('读取', refreshError));
    } finally {
      if (version === requestVersion.current && currentTaskId.current === requestedTaskId) {
        setLoading(false);
      }
    }
  }, [taskId]);

  useEffect(() => {
    requestVersion.current += 1;
    setItems([]);
    setBusyId(null);
    setError(null);
    setToast(null);
    void refresh();
    const id = window.setInterval(() => void refresh(), 8000);
    return () => {
      requestVersion.current += 1;
      window.clearInterval(id);
    };
  }, [refresh, taskId]);

  const transition = async (id: string, action: 'confirm' | 'reject') => {
    const requestedTaskId = taskId;
    const item = items.find((candidate) => candidate.id === id);
    if (!requestedTaskId || item?.task_id !== requestedTaskId || item.status !== 'proposed') {
      setError('变更已切换或状态已更新，请核对最新结果');
      return;
    }
    setBusyId(id);
    setError(null);
    try {
      const { change } =
        action === 'confirm' ? await confirmPicoChange(id) : await rejectPicoChange(id);
      if (currentTaskId.current !== requestedTaskId) {
        return;
      }
      setItems((current) =>
        current.map((candidate) => (candidate.id === change.id ? change : candidate)),
      );
      await refresh();
      if (currentTaskId.current !== requestedTaskId) {
        return;
      }
      setToast(action === 'confirm' ? '变更已确认，状态已刷新' : '变更已拒绝，状态已刷新');
      void Promise.resolve(onChanged?.()).catch(() => undefined);
    } catch (transitionError) {
      if (currentTaskId.current !== requestedTaskId) {
        return;
      }
      await refresh();
      if (currentTaskId.current === requestedTaskId) {
        setError(safeChangeError(action === 'confirm' ? '确认' : '拒绝', transitionError));
      }
    } finally {
      setBusyId((current) => (current === id ? null : current));
    }
  };

  useEffect(() => {
    if (!toast) {
      return;
    }
    const timeout = window.setTimeout(() => setToast(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [toast]);

  if (!taskId || (!items.length && !error)) {
    return null;
  }

  const hasPending = items.some((item) => item.status === 'proposed');
  let heading = '业务变更确认状态（S7）';
  if (hasPending) {
    heading = '待确认业务变更（S7）';
  } else if (items.length) {
    heading = '业务变更确认记录（S7）';
  }

  return (
    <div className="border-b border-amber-200 bg-amber-50 px-3 py-2 text-[12.5px] text-amber-950">
      <div className="mb-1.5 flex items-center gap-1.5 font-medium">
        <FileWarning className="h-3.5 w-3.5" />
        <span>{heading}</span>
        {loading ? <Loader2 className="h-3 w-3 animate-spin opacity-60" /> : null}
      </div>
      {error ? <p className="mb-1 text-[11px] text-red-700">{error}</p> : null}
      {toast ? <p className="mb-1 text-[11px] text-emerald-800">{toast}</p> : null}
      {items.length ? (
        <ul className="space-y-2">
          {items.map((change) => {
            const title = change.title.trim() || '未命名变更';
            const summary = change.summary.trim() || '未提供变更摘要';
            return (
              <li
                key={change.id}
                className="flex flex-wrap items-start justify-between gap-2 rounded-lg bg-white/90 px-2.5 py-2 ring-1 ring-amber-100"
              >
                <div className="min-w-0 flex-1">
                  <p className="break-words font-medium text-[#1a1a1a]" title={title}>
                    {title}
                  </p>
                  <p className="mt-0.5 line-clamp-2 text-[11.5px] text-[#6b6b6b]" title={summary}>
                    {summary}
                  </p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1.5">
                  <span
                    className={cn(
                      'rounded-md px-2 py-1 text-[11px] font-medium',
                      STATUS_CLASS[change.status],
                    )}
                  >
                    {STATUS_LABEL[change.status]}
                  </span>
                  {change.status === 'proposed' && change.task_id === taskId ? (
                    <div className="flex items-center gap-1">
                      <button
                        type="button"
                        disabled={busyId === change.id}
                        onClick={() => void transition(change.id, 'confirm')}
                        className={cn(
                          'inline-flex items-center gap-1 rounded-md bg-[#1a1a1a] px-2 py-1 text-[11px] font-medium text-white',
                          busyId === change.id && 'opacity-50',
                        )}
                      >
                        <Check className="h-3 w-3" />
                        {CONFIRM_LABEL}
                      </button>
                      <button
                        type="button"
                        disabled={busyId === change.id}
                        onClick={() => void transition(change.id, 'reject')}
                        className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-[11px] font-medium text-red-700 ring-1 ring-red-200"
                      >
                        <X className="h-3 w-3" />
                        {REJECT_LABEL}
                      </button>
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
