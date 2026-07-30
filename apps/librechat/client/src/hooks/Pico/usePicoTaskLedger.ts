import { useCallback, useEffect, useState } from 'react';
import {
  getPicoTask,
  listPicoTaskRuns,
  listPicoTasks,
  rebindConversation,
  type PicoArtifact,
  type PicoRun,
  type PicoTask,
} from '~/data-provider/pico/api';

export type PicoLedgerState = {
  task: PicoTask | null;
  run: PicoRun | null;
  artifacts: PicoArtifact[];
  statusLabel: string | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
};

function statusLabel(
  run: PicoRun | null,
  isSubmitting: boolean,
  artifacts: PicoArtifact[],
): string | null {
  if (isSubmitting) {
    return '等待模型响应';
  }
  if (!run) {
    if (artifacts.length) {
      return '已完成';
    }
    return null;
  }
  if (run.status === 'running' || run.status === 'queued' || run.status === 'preparing') {
    return '等待模型响应';
  }
  if (run.status === 'succeeded') {
    if (run.started_at && run.ended_at) {
      const ms = Date.parse(run.ended_at) - Date.parse(run.started_at);
      if (!Number.isNaN(ms) && ms > 0) {
        return `已完成 ${Math.max(1, Math.round(ms / 1000))}s`;
      }
    }
    return '已完成';
  }
  if (run.status === 'failed') {
    return run.error ? `失败：${run.error.slice(0, 40)}` : '失败';
  }
  if (run.status === 'cancelled') {
    return '已取消';
  }
  return run.status;
}

function readPendingId(): string | null {
  try {
    const p = sessionStorage.getItem('pico:pendingConvo');
    if (p && p.startsWith('pending_')) {
      return p;
    }
    const from = sessionStorage.getItem('pico:rebindFrom');
    if (from && from.startsWith('pending_')) {
      return from;
    }
  } catch {
    /* ignore */
  }
  return null;
}

export function usePicoTaskLedger(
  conversationId: string | undefined | null,
  isSubmitting: boolean,
): PicoLedgerState {
  const [task, setTask] = useState<PicoTask | null>(null);
  const [run, setRun] = useState<PicoRun | null>(null);
  const [artifacts, setArtifacts] = useState<PicoArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((n) => n + 1), []);

  // Rebind pending_* → real conversation id once LibreChat assigns one
  useEffect(() => {
    if (!conversationId || conversationId === 'new' || conversationId.startsWith('pending_')) {
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        let from = sessionStorage.getItem('pico:rebindFrom');
        const to = sessionStorage.getItem('pico:rebindTo') || conversationId;
        if (!from) {
          const pending = sessionStorage.getItem('pico:pendingConvo');
          if (pending && pending.startsWith('pending_') && pending !== conversationId) {
            from = pending;
          }
        }
        if (from && from.startsWith('pending_') && to && to !== from) {
          const result = await rebindConversation(from, to);
          if (!cancelled && result.updated > 0) {
            sessionStorage.removeItem('pico:rebindFrom');
            sessionStorage.removeItem('pico:rebindTo');
            sessionStorage.removeItem('pico:pendingConvo');
            setTick((n) => n + 1);
          }
        }
      } catch {
        /* retry on next tick */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, tick]);

  useEffect(() => {
    if (!conversationId || conversationId === 'new') {
      setTask(null);
      setRun(null);
      setArtifacts([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        // Query real id first; if empty (first msg race), also try pending_*
        let tasks = (await listPicoTasks(conversationId)).tasks || [];
        if (!tasks.length) {
          const pending = readPendingId();
          if (pending && pending !== conversationId) {
            tasks = (await listPicoTasks(pending)).tasks || [];
          }
        }
        const latest = tasks[0] ?? null;
        if (cancelled) {
          return;
        }
        setTask(latest);
        if (!latest) {
          setRun(null);
          setArtifacts([]);
          return;
        }
        const [detail, runsRes] = await Promise.all([
          getPicoTask(latest.id),
          listPicoTaskRuns(latest.id),
        ]);
        if (cancelled) {
          return;
        }
        setArtifacts(detail.artifacts || []);
        const runs = runsRes.runs || [];
        setRun(runs[0] ?? null);
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          // user-facing short Chinese for common fetch failures
          if (msg.includes('401')) {
            setError('登录已失效，请刷新页面后重新登录');
          } else if (msg.includes('502') || msg.includes('unavailable')) {
            setError('账本服务暂时不可用，请稍后重试');
          } else {
            setError(msg.slice(0, 120));
          }
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, [conversationId, tick, isSubmitting]);

  // poll while submitting + short tail after finish (artifacts may lag)
  useEffect(() => {
    if (!conversationId || conversationId === 'new') {
      return;
    }
    if (isSubmitting) {
      const id = window.setInterval(() => setTick((n) => n + 1), 2000);
      return () => window.clearInterval(id);
    }
    // after submit ends, refresh a few times for artifact
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      setTick((t) => t + 1);
      if (n >= 4) {
        window.clearInterval(id);
      }
    }, 1500);
    return () => window.clearInterval(id);
  }, [isSubmitting, conversationId]);

  return {
    task,
    run,
    artifacts,
    statusLabel: statusLabel(run, isSubmitting, artifacts),
    loading,
    error,
    refresh,
  };
}
