import { useCallback, useEffect, useRef, useState } from 'react';
import {
  cancelPicoRun,
  getPicoTask,
  listPicoRunEvents,
  listPicoTaskRuns,
  listPicoTasks,
  rebindConversation,
  retryPicoRun,
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
  /** Live one-line process for the task bar while a run is active. */
  processHint: string | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
  cancelling: boolean;
  cancelRun: (runId?: string) => Promise<void>;
  rerunning: boolean;
  rerunFailedRun: (runId?: string) => Promise<void>;
};

const ACTIVE_RUN_STATUSES = new Set(['queued', 'running', 'preparing']);
/** How many newest tasks to inspect when recovering an active Run after reload. */
const ACTIVE_RUN_SCAN_LIMIT = 5;
const RECOVERY_WINDOW_MS = 30_000;

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

export function recoveryTaskCandidates(
  tasks: PicoTask[],
  trackedTaskId: string | null,
  exhaustive: boolean,
): PicoTask[] {
  if (exhaustive || tasks.length <= ACTIVE_RUN_SCAN_LIMIT) {
    return tasks;
  }
  const candidates = tasks.slice(0, ACTIVE_RUN_SCAN_LIMIT);
  const tracked = trackedTaskId
    ? tasks.find((candidate) => candidate.id === trackedTaskId)
    : undefined;
  if (tracked && !candidates.some((candidate) => candidate.id === tracked.id)) {
    candidates.push(tracked);
  }
  return candidates;
}

export function failedRunUserMessage(events: PicoRunEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.type !== 'run.status' && event.type !== 'run.error') {
      continue;
    }
    const userMessage = event.payload?.user_message;
    if (typeof userMessage === 'string' && userMessage.trim()) {
      return userMessage.trim();
    }
  }
  return null;
}

function friendlyFailureLabel(run: PicoRun, events: PicoRunEvent[]): string {
  const userMessage = failedRunUserMessage(events);
  if (userMessage) {
    return `失败：${userMessage}`;
  }
  const raw = (run.error || '').trim();
  if (!raw) {
    return '失败';
  }
  // Keep technical stacks out of the task bar.
  if (/traceback|filenotfound|sqlite|toolcall|event_contract/i.test(raw)) {
    return '失败：智能体任务未正常完成，请重试';
  }
  return `失败：${raw.slice(0, 40)}`;
}

function runtimeHint(events: PicoRunEvent[]): string | null {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.type !== 'run.status') {
      continue;
    }
    const runtime = event.payload?.runtime;
    if (runtime === 'kimi-agent') {
      return 'Kimi Agent';
    }
  }
  return null;
}

function processHint(run: PicoRun | null, events: PicoRunEvent[]): string | null {
  if (!isActiveRun(run)) {
    return null;
  }
  if (run.cancel_requested) {
    return '停止请求已提交，等待任务结束';
  }
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (event.type === 'tool.call') {
      const tool = event.payload?.tool ?? event.payload?.name;
      if (typeof tool === 'string' && tool.trim()) {
        return `正在调用 · ${tool.trim()}`;
      }
    }
    if (event.type === 'tool.result') {
      const tool = event.payload?.tool ?? event.payload?.name;
      if (typeof tool === 'string' && tool.trim()) {
        const ok = event.payload?.ok !== false;
        return ok ? `工具完成 · ${tool.trim()}` : `工具失败 · ${tool.trim()}`;
      }
    }
    if (event.type === 'agent.step') {
      const n = event.payload?.n ?? event.payload?.step;
      const phase = event.payload?.phase;
      const bits = [
        typeof n === 'number' || typeof n === 'string' ? `步骤 ${n}` : '智能体步骤',
        typeof phase === 'string' && phase.trim() ? phase.trim() : null,
      ].filter(Boolean);
      return bits.join(' · ');
    }
  }
  const runtime = runtimeHint(events);
  return runtime ? `运行中 · ${runtime}` : '正在处理…';
}

function statusLabel(
  run: PicoRun | null,
  isSubmitting: boolean,
  artifacts: PicoArtifact[],
  events: PicoRunEvent[] = [],
): string | null {
  if (run?.cancel_requested && isActiveRun(run)) {
    return '正在停止';
  }
  if (run?.status === 'cancelled') {
    return '已停止';
  }
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
    const runtime = runtimeHint(events);
    return runtime ? `等待模型响应 · ${runtime}` : '等待模型响应';
  }
  if (run.status === 'succeeded') {
    const runtime = runtimeHint(events);
    let base = '已完成';
    if (run.started_at && run.ended_at) {
      const ms = Date.parse(run.ended_at) - Date.parse(run.started_at);
      if (!Number.isNaN(ms) && ms > 0) {
        base = `已完成 ${Math.max(1, Math.round(ms / 1000))}s`;
      }
    }
    const artN = artifacts.length;
    if (artN > 0) {
      base = `${base} · ${artN} 个产物`;
    }
    return runtime ? `${base} · ${runtime}` : base;
  }
  if (run.status === 'failed') {
    return friendlyFailureLabel(run, events);
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
  const [rerunRequestInFlight, setRerunRequestInFlight] = useState(false);
  const [cancelRequestedRunId, setCancelRequestedRunId] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [rerunError, setRerunError] = useState<string | null>(null);
  const [recovering, setRecovering] = useState(true);
  const [tick, setTick] = useState(0);
  const activeRun = isActiveRun(run);
  const runRef = useRef(run);
  const taskRef = useRef(task);
  const recoveryDeadlineRef = useRef(0);
  runRef.current = run;
  taskRef.current = task;

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
  const rerunFailedRun = useCallback(
    async (runId?: string) => {
      const targetRunId = runId ?? (run?.status === 'failed' ? run.id : undefined);
      if (!targetRunId) {
        setRerunError('重新运行失败：未找到失败的任务');
        return;
      }
      setRerunRequestInFlight(true);
      setRerunError(null);
      try {
        const result = await retryPicoRun(targetRunId);
        setRun(result.run);
        setEvents([]);
        setTick((n) => n + 1);
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        if (message.includes('401')) {
          setRerunError('重新运行失败：登录已失效，请刷新页面后重新登录');
        } else if (message.includes('404')) {
          setRerunError('重新运行失败：运行不存在或无权限');
        } else if (message.includes('409')) {
          setRerunError('重新运行失败：该任务当前不可重跑，请刷新后再试');
        } else if (message.includes('502') || message.includes('unavailable')) {
          setRerunError('重新运行失败：账本服务暂时不可用，请稍后重试');
        } else {
          setRerunError('重新运行失败，请稍后重试');
        }
      } finally {
        setRerunRequestInFlight(false);
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
    setTask(null);
    setRun(null);
    setEvents([]);
    setArtifacts([]);
    setCancelError(null);
    setRerunError(null);
    setCancelRequestedRunId(null);
    runRef.current = null;
    taskRef.current = null;
    if (!conversationId || conversationId === 'new') {
      recoveryDeadlineRef.current = 0;
      setRecovering(false);
      return;
    }
    recoveryDeadlineRef.current = Date.now() + RECOVERY_WINDOW_MS;
    setRecovering(true);
    const timeout = window.setTimeout(() => {
      recoveryDeadlineRef.current = 0;
      setRecovering(false);
    }, RECOVERY_WINDOW_MS);
    return () => window.clearTimeout(timeout);
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

        const scan = recoveryTaskCandidates(
          tasks,
          taskRef.current?.id ?? null,
          recoveryDeadlineRef.current > Date.now(),
        );
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
        taskRef.current = preferred.task;
        setArtifacts(detail.artifacts || []);
        setRun(preferred.run);
        recoveryDeadlineRef.current = 0;
        setRecovering(false);
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
    if (isSubmitting || activeRun || recovering) {
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
  }, [isSubmitting, conversationId, activeRun, recovering]);

  return {
    task,
    run,
    events,
    artifacts,
    statusLabel: statusLabel(run, isSubmitting, artifacts, events),
    processHint: processHint(run, events),
    loading,
    error: rerunError ?? cancelError ?? loadError,
    refresh,
    cancelling:
      cancelRequestInFlight ||
      Boolean(run?.cancel_requested && isActiveRun(run)) ||
      Boolean(cancelRequestedRunId && cancelRequestedRunId === run?.id && isActiveRun(run)),
    cancelRun,
    rerunning: rerunRequestInFlight,
    rerunFailedRun,
  };
}
