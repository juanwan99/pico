import { useCallback, useEffect, useRef, useState } from 'react';
import {
  cancelPicoRun,
  cancelPicoTaskActiveRuns,
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
import { latestArtifactsByFilename } from '~/utils/picoLatestArtifacts';
import { workbenchToolResultLine, workbenchToolStepLine } from '~/utils/picoWorkbenchProgress';

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

/** Do not let an older poll undo a locally acknowledged stop for the same Run. */
export function mergePolledRun(current: PicoRun | null, incoming: PicoRun | null): PicoRun | null {
  if (!current || !incoming || current.id !== incoming.id) {
    return incoming;
  }
  if (current.status === 'cancelled' && isActiveRun(incoming)) {
    return current;
  }
  if (
    isActiveRun(current) &&
    current.cancel_requested &&
    isActiveRun(incoming) &&
    !incoming.cancel_requested
  ) {
    return current;
  }
  return incoming;
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

/** Client fallback when ledger events lack user_message (older tips / raw error). */
export function mapRawRunErrorToUserMessage(raw: string): string {
  const text = raw.trim();
  const low = text.toLowerCase();
  if (!text) {
    return '出了点问题，请重试';
  }
  if (low.includes('owner was lost') || low.includes('api restart') || low.includes('greenlet')) {
    return '服务维护或重启导致本次任务中断。请点「重新运行」继续';
  }
  if (/traceback|filenotfound|sqlite|toolcall|event_contract/i.test(text)) {
    return '智能体任务未正常完成，请重试';
  }
  if (text.length > 80) {
    return '服务暂时出错，请点「重新运行」或稍后重试';
  }
  return text;
}

export function friendlyFailureLabel(run: PicoRun, events: PicoRunEvent[]): string {
  const userMessage = failedRunUserMessage(events);
  if (userMessage) {
    return `失败：${userMessage}`;
  }
  const raw = (run.error || '').trim();
  if (!raw) {
    return '失败';
  }
  return `失败：${mapRawRunErrorToUserMessage(raw)}`;
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

function toolName(event: PicoRunEvent): string | null {
  const value = event.payload?.tool ?? event.payload?.name;
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

function describeSearchOrTool(event: PicoRunEvent): string | null {
  if (event.type === 'search.sources') {
    const sources = Array.isArray(event.payload?.sources) ? event.payload.sources : [];
    if (event.payload?.honest_miss === true || sources.length === 0) {
      return '未检索到可用来源';
    }
    return `已检索 ${sources.length} 条来源`;
  }
  if (event.type === 'tool.call') {
    const tool = toolName(event);
    if (!tool) {
      return null;
    }
    const fromEvent = event.payload?.step_line;
    if (typeof fromEvent === 'string' && fromEvent.trim()) {
      return fromEvent.trim();
    }
    return workbenchToolStepLine(tool);
  }
  if (event.type === 'tool.result') {
    const tool = toolName(event);
    if (!tool) {
      return null;
    }
    const ok = event.payload?.ok !== false;
    const userMessage = event.payload?.user_message;
    if (!ok && typeof userMessage === 'string' && userMessage.trim()) {
      return userMessage.trim();
    }
    return workbenchToolResultLine(tool, ok);
  }
  if (event.type === 'compaction.begin' || event.type === 'compaction.end') {
    const text = event.payload?.text;
    if (typeof text === 'string' && text.trim()) {
      return text.trim();
    }
    return '在整理上文';
  }
  return null;
}

export function lastProcessStep(events: PicoRunEvent[]): string | null {
  let latestTool: string | null = null;
  let latestAgent: string | null = null;
  for (let i = events.length - 1; i >= 0; i -= 1) {
    const event = events[i];
    if (!latestTool) {
      latestTool = describeSearchOrTool(event);
    }
    if (!latestAgent && event.type === 'agent.step') {
      const n = event.payload?.n ?? event.payload?.step;
      const phase = event.payload?.phase;
      latestAgent = [
        typeof n === 'number' || typeof n === 'string' ? `步骤 ${n}` : '智能体步骤',
        typeof phase === 'string' && phase.trim() ? phase.trim() : null,
      ]
        .filter(Boolean)
        .join(' · ');
    }
    if (latestTool && latestAgent) {
      break;
    }
  }
  // Search/tool copy wins over later bookkeeping agent.step so「正在检索」stays.
  return latestTool || latestAgent;
}

export function composeProcessHint(run: PicoRun | null, events: PicoRunEvent[]): string | null {
  // Teachers need a fixed process strip: runtime · step/tool · terminal when known.
  const runtime = runtimeHint(events);
  const step = lastProcessStep(events);
  if (run?.cancel_requested && isActiveRun(run)) {
    return ['停止请求已提交', runtime, step].filter(Boolean).join(' · ');
  }
  if (isActiveRun(run)) {
    // Package B: job lives on the server; tab close does not stop it.
    const cloud = '云端继续中';
    if (step) {
      return [cloud, runtime, step].filter(Boolean).join(' · ');
    }
    return runtime
      ? `${cloud} · ${runtime} · 正在检索或作答`
      : `${cloud} · 正在检索或作答`;
  }
  if (!run && !runtime && !step) {
    return null;
  }
  const terminal =
    run?.status === 'succeeded'
      ? '终态 · 成功'
      : run?.status === 'failed'
        ? '终态 · 失败'
        : run?.status === 'cancelled'
          ? '终态 · 已停止'
          : null;
  const settledStep = step && step.includes('正在') ? null : step;
  const bits = [runtime ? `运行时 · ${runtime}` : null, settledStep, terminal].filter(Boolean);
  return bits.length ? bits.join(' · ') : null;
}

/**
 * Ledger terminal status always wins over client stream ``isSubmitting``.
 * Prevents「侧栏失败 / 主区永久正在准备」when the API restarted mid-run.
 */
export function computeRunStatusLabel(
  run: PicoRun | null,
  isSubmitting: boolean,
  artifacts: PicoArtifact[],
  events: PicoRunEvent[] = [],
): string | null {
  if (run?.cancel_requested && isActiveRun(run)) {
    return '正在停止';
  }
  // Terminal first — never mask failure/cancel behind local stream flags.
  if (run?.status === 'cancelled') {
    return '已停止';
  }
  if (run?.status === 'failed') {
    return friendlyFailureLabel(run, events);
  }
  if (run?.status === 'succeeded') {
    const runtime = runtimeHint(events);
    let base = '已完成';
    if (run.started_at && run.ended_at) {
      const ms = Date.parse(run.ended_at) - Date.parse(run.started_at);
      if (!Number.isNaN(ms) && ms > 0) {
        base = `已完成 ${Math.max(1, Math.round(ms / 1000))}s`;
      }
    }
    const artN = artifacts.filter(
      (a) => !(a.kind === 'doc' && (a.title || '').trim() === '回复摘要'),
    ).length;
    if (artN > 0) {
      base = `${base} · ${artN} 个可下载文件`;
    }
    return runtime ? `${base} · ${runtime}` : base;
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
    // Durable default: ledger is source of truth after reload / tab close.
    return runtime ? `云端运行中 · ${runtime}` : '云端运行中（关闭页面不中断）';
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
  const cancelRequestRunIdRef = useRef<string | null>(null);
  const cancelErrorRunIdRef = useRef<string | null>(null);
  runRef.current = run;
  taskRef.current = task;

  const refresh = useCallback(() => setTick((n) => n + 1), []);
  const cancelRun = useCallback(async (runId?: string) => {
    const currentRun = runRef.current;
    const targetRunId = runId ?? (isActiveRun(currentRun) ? currentRun.id : undefined);
    const taskId = taskRef.current?.id;
    // Allow cancel by task when stream is live but run id not yet bound (V-D).
    if (!targetRunId) {
      if (!taskId) {
        setCancelError('停止运行失败：未找到正在运行的任务');
        return;
      }
      setCancelRequestInFlight(true);
      setCancelError(null);
      try {
        const batch = await cancelPicoTaskActiveRuns(taskId);
        const resultRun = batch.runs[0] ?? null;
        if (resultRun) {
          runRef.current = resultRun;
          setRun(resultRun);
        }
        setTick((n) => n + 1);
      } catch (e) {
        const message = e instanceof Error ? e.message : String(e);
        setCancelError(
          message.includes('401')
            ? '停止运行失败：登录已失效，请刷新页面后重新登录'
            : '停止运行失败，请稍后重试',
        );
      } finally {
        setCancelRequestInFlight(false);
      }
      return;
    }
    if (currentRun?.id === targetRunId && !isActiveRun(currentRun)) {
      setCancelError('停止运行失败：未找到正在运行的任务');
      return;
    }
    if (
      (currentRun?.id === targetRunId && currentRun.cancel_requested) ||
      cancelRequestRunIdRef.current === targetRunId
    ) {
      return;
    }
    cancelRequestRunIdRef.current = targetRunId;
    cancelErrorRunIdRef.current = null;
    setCancelRequestInFlight(true);
    setCancelRequestedRunId(targetRunId);
    setCancelError(null);
    try {
      let resultRun: PicoRun | null = null;
      try {
        const result = await cancelPicoRun(targetRunId);
        resultRun = result.run;
      } catch (firstError) {
        const message = firstError instanceof Error ? firstError.message : String(firstError);
        if (taskId && (message.includes('409') || message.includes('404'))) {
          const batch = await cancelPicoTaskActiveRuns(taskId);
          resultRun = batch.runs[0] ?? runRef.current;
        } else {
          throw firstError;
        }
      }
      if (resultRun) {
        runRef.current = resultRun;
        setRun(resultRun);
      }
      cancelErrorRunIdRef.current = null;
      if (!resultRun || !isActiveRun(resultRun)) {
        cancelRequestRunIdRef.current = null;
        setCancelRequestedRunId(null);
      } else if (!resultRun.cancel_requested) {
        cancelRequestRunIdRef.current = null;
        setCancelRequestedRunId(null);
      }
      setTick((n) => n + 1);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      cancelErrorRunIdRef.current = targetRunId;
      cancelRequestRunIdRef.current = null;
      if (message.includes('401')) {
        setCancelError('停止运行失败：登录已失效，请刷新页面后重新登录');
      } else if (message.includes('403')) {
        setCancelError('停止运行失败：当前账号没有停止权限');
      } else if (message.includes('404')) {
        setCancelError('停止运行失败：运行不存在或无权限');
      } else if (message.includes('409')) {
        setCancelError('停止运行失败：任务已结束，请核对最新状态');
      } else if (message.includes('502') || message.includes('unavailable')) {
        setCancelError('停止运行失败：账本服务暂时不可用，请稍后重试');
      } else {
        setCancelError('停止运行失败，请稍后重试');
      }
      setCancelRequestedRunId(null);
      setTick((n) => n + 1);
    } finally {
      setCancelRequestInFlight(false);
    }
  }, []);

  useEffect(() => {
    if (!run || !isActiveRun(run)) {
      cancelRequestRunIdRef.current = null;
    } else if (run.cancel_requested) {
      cancelRequestRunIdRef.current = run.id;
    }
    const failedRunId = cancelErrorRunIdRef.current;
    if (
      cancelError &&
      failedRunId &&
      (!run || run.id !== failedRunId || !isActiveRun(run) || Boolean(run.cancel_requested))
    ) {
      cancelErrorRunIdRef.current = null;
      setCancelError(null);
    }
  }, [cancelError, run]);
  const rerunFailedRun = useCallback(
    async (runId?: string) => {
      const current = runRef.current;
      // H8: terminal runs (failed/succeeded/cancelled) may be re-run
      const terminal =
        current &&
        ['failed', 'succeeded', 'cancelled'].includes(current.status || '');
      const targetRunId = runId ?? (terminal ? current.id : undefined);
      if (!targetRunId) {
        setRerunError('重新运行失败：未找到可重跑的任务');
        return;
      }
      setRerunRequestInFlight(true);
      setRerunError(null);
      try {
        const result = await retryPicoRun(targetRunId);
        runRef.current = result.run;
        setRun(result.run);
        setEvents([]);
        setCancelError(null);
        setCancelRequestedRunId(null);
        cancelRequestRunIdRef.current = null;
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
    [],
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
    cancelRequestRunIdRef.current = null;
    cancelErrorRunIdRef.current = null;
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
        setArtifacts(latestArtifactsByFilename(detail.artifacts || []));
        const nextRun = mergePolledRun(runRef.current, preferred.run);
        runRef.current = nextRun;
        setRun(nextRun);
        recoveryDeadlineRef.current = 0;
        setRecovering(false);
        if (!nextRun) {
          if (!cancelled) {
            setEvents([]);
          }
          return;
        }
        try {
          const eventsRes = await listPicoRunEvents(nextRun.id);
          // Apply even if this effect was superseded: a 500ms terminal poll
          // must not drop search.sources that already landed for this run.
          if (runRef.current?.id === nextRun.id) {
            setEvents(eventsRes.events || []);
          }
        } catch {
          // Keep whatever we already have — empty wipe hid 来源条 (#537).
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
    // #461 PR-A2: trigger immediately + tighter poll so multi-file chips (e.g.
    // C2 5 files) render in ~1s instead of lagging 4×1.5s after settle — avoids
    // "ledger green but UI shows fewer files" on first paint after completion.
    let n = 0;
    setTick((t) => t + 1);
    const id = window.setInterval(() => {
      n += 1;
      setTick((t) => t + 1);
      if (n >= 6) {
        window.clearInterval(id);
      }
    }, 500);
    return () => window.clearInterval(id);
  }, [isSubmitting, conversationId, activeRun, recovering]);

  return {
    task,
    run,
    events,
    artifacts,
    statusLabel: computeRunStatusLabel(run, isSubmitting, artifacts, events),
    processHint: composeProcessHint(run, events),
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
