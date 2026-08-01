import { useCallback, useEffect, useRef, useState } from 'react';
import {
  cancelPicoRun,
  getPicoTask,
  listPicoRunEvents,
  listPicoTaskRuns,
  listPicoTasks,
  rebindConversation,
  type PicoArtifact,
  type PicoRun,
  type PicoRunEvent,
  type PicoTask,
} from '~/data-provider/pico/api';

export type PicoLedgerState = {
  task: PicoTask | null;
  run: PicoRun | null;
  events: PicoRunEvent[];
  artifacts: PicoArtifact[];
  statusLabel: string | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  cancelling: boolean;
  cancelRun: (runId?: string) => Promise<void>;
};

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'preparing']);
/** How many newest tasks to inspect when recovering an active Run after reload. */
const ACTIVE_RUN_SCAN_LIMIT = 5;

function isActiveRun(run: PicoRun | null | undefined): run is PicoRun {
  return Boolean(run && ACTIVE_RUN_STATUSES.has(run.status));
}

/** Prefer an active Run over a merely newest terminal Run (runs are newest-first). */
export function pickPreferredRun(runs: PicoRun[]): PicoRun | null {
  if (!runs.length) {
    return null;
  }
  return runs.find((r) => isActiveRun(r)) ?? runs[0] ?? null;
}

/**
 * Among the newest conversation tasks, prefer one whose ledger still has an
 * active Run so reload keeps following progress instead of freezing on a
 * newer terminal task that would only get the short tail poll.
 */
export function pickPreferredTaskRuns(
  entries: Array<{ task: PicoTask; runs: PicoRun[] }>,
): { task: PicoTask; run: PicoRun | null; runs: PicoRun[] } | null {
  if (!entries.length) {
    return null;
  }
  const withActive = entries.find((entry) => entry.runs.some((r) => isActiveRun(r)));
  const chosen = withActive ?? entries[0];
  return {
    task: chosen.task,
    runs: chosen.runs,
    run: pickPreferredRun(chosen.runs),
  };
}

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
  if (isActiveRun(run)) {
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
  const [events, setEvents] = useState<PicoRunEvent[]>([]);
  const [artifacts, setArtifacts] = useState<PicoArtifact[]>([]);
  const [loading, setLoading] = useState(false);
  const [cancelRequestInFlight, setCancelRequestInFlight] = useState(false);
  const [cancelRequestedRunId, setCancelRequestedRunId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const activeRun = isActiveRun(run);
  const runRef = useRef(run);
  runRef.current = run;

  const refresh = useCallback(() => setTick((n) => n + 1), []);
  const cancelRun = useCallback(
    async (runId?: string) => {
      const targetRunId = runId ?? (isActiveRun(run) ? run.id : undefined);
      if (!targetRunId) {
        setCancelError('停止运行失败：未找到正在运行的任务');
        return;
      }
      setCancelRequestInFlight(true);
      setCancelRequestedRunId(targetRunId);
      setCancelError(null);
      try {
        const result = await cancelPicoRun(targetRunId);
        setRun(result.run);
        if (!isActiveRun(result.run)) {
          setCancelRequestedRunId(null);
        }
        setTick((n) => n + 1);
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        if (message.includes('401')) {
          setCancelError('停止运行失败：登录已失效，请刷新页面后重新登录');
        } else if (message.includes('404')) {
          setCancelError('停止运行失败：运行不存在或无权限');
        } else if (message.includes('502') || message.includes('unavailable')) {
          setCancelError('停止运行失败：账本服务暂时不可用，请稍后重试');
        } else {
          setCancelError('停止运行失败，请稍后重试');
        }
        setCancelRequestedRunId(null);
      } finally {
        setCancelRequestInFlight(false);
      }
    },
    [run],
  );

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
    setCancelError(null);
    setCancelRequestedRunId(null);
  }, [conversationId]);

  useEffect(() => {
    if (!conversationId || conversationId === 'new') {
      setTask(null);
      setRun(null);
      setEvents([]);
      setArtifacts([]);
      return;
    }
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setLoadError(null);
      try {
        // Query real id first; if empty (first msg race), also try pending_*
        let tasks = (await listPicoTasks(conversationId)).tasks || [];
        if (!tasks.length) {
          const pending = readPendingId();
          if (pending && pending !== conversationId) {
            tasks = (await listPicoTasks(pending)).tasks || [];
          }
        }
        if (cancelled) {
          return;
        }
        if (!tasks.length) {
          // Transient empty list must not drop an active Run we already follow
          // (reload recovery would otherwise fall into the short terminal tail).
          if (!isActiveRun(runRef.current)) {
            setTask(null);
            setRun(null);
            setEvents([]);
            setArtifacts([]);
          }
          return;
        }

        const scan = tasks.slice(0, ACTIVE_RUN_SCAN_LIMIT);
        const entries = await Promise.all(
          scan.map(async (candidate) => ({
            task: candidate,
            runs: (await listPicoTaskRuns(candidate.id)).runs || [],
          })),
        );
        if (cancelled) {
          return;
        }

        const preferred = pickPreferredTaskRuns(entries);
        if (!preferred) {
          if (!isActiveRun(runRef.current)) {
            setTask(null);
            setRun(null);
            setEvents([]);
            setArtifacts([]);
          }
          return;
        }

        const detail = await getPicoTask(preferred.task.id);
        if (cancelled) {
          return;
        }

        setTask(preferred.task);
        setArtifacts(detail.artifacts || []);
        setRun(preferred.run);
        if (!preferred.run) {
          setEvents([]);
          return;
        }
        try {
          const eventsRes = await listPicoRunEvents(preferred.run.id);
          if (!cancelled) {
            setEvents(eventsRes.events || []);
          }
        } catch {
          if (!cancelled) {
            setEvents([]);
          }
        }
      } catch (e) {
        if (!cancelled) {
          const msg = e instanceof Error ? e.message : String(e);
          // user-facing short Chinese for common fetch failures
          if (msg.includes('401')) {
            setLoadError('登录已失效，请刷新页面后重新登录');
          } else if (msg.includes('502') || msg.includes('unavailable')) {
            setLoadError('账本服务暂时不可用，请稍后重试');
          } else {
            setLoadError(msg.slice(0, 120));
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

  // The ledger is the source of truth after reload: keep polling an active Run
  // even when LibreChat no longer has the original in-memory submitting state.
  useEffect(() => {
    if (!conversationId || conversationId === 'new') {
      return;
    }
    if (isSubmitting || activeRun) {
      const id = window.setInterval(() => setTick((n) => n + 1), 2000);
      return () => window.clearInterval(id);
    }
    // After the ledger reaches a terminal state, refresh a few times for artifacts.
    let n = 0;
    const id = window.setInterval(() => {
      n += 1;
      setTick((t) => t + 1);
      if (n >= 4) {
        window.clearInterval(id);
      }
    }, 1500);
    return () => window.clearInterval(id);
  }, [isSubmitting, conversationId, activeRun]);

  return {
    task,
    run,
    events,
    artifacts,
    statusLabel: statusLabel(run, isSubmitting, artifacts),
    loading,
    error: cancelError ?? loadError,
    refresh,
    cancelling:
      cancelRequestInFlight ||
      Boolean(cancelRequestedRunId && cancelRequestedRunId === run?.id && isActiveRun(run)),
    cancelRun,
  };
}
