import { useCallback, useEffect, useState } from 'react';
import {
  getPicoTask,
  listPicoTaskRuns,
  listPicoTasks,
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

function statusLabel(run: PicoRun | null, isSubmitting: boolean): string | null {
  if (isSubmitting) {
    return '等待模型响应';
  }
  if (!run) {
    return null;
  }
  if (run.status === 'running' || run.status === 'queued' || run.status === 'preparing') {
    return '等待模型响应';
  }
  if (run.status === 'succeeded') {
    if (run.started_at && run.ended_at) {
      const ms =
        Date.parse(run.ended_at) - Date.parse(run.started_at);
      if (!Number.isNaN(ms) && ms > 0) {
        return `已完成 ${Math.max(1, Math.round(ms / 1000))}s`;
      }
    }
    return '已完成';
  }
  if (run.status === 'failed') {
    return '失败';
  }
  if (run.status === 'cancelled') {
    return '已取消';
  }
  return run.status;
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
        const { tasks } = await listPicoTasks(conversationId);
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
          setError(e instanceof Error ? e.message : String(e));
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

  // poll while submitting
  useEffect(() => {
    if (!isSubmitting || !conversationId || conversationId === 'new') {
      return;
    }
    const id = window.setInterval(() => setTick((n) => n + 1), 2500);
    return () => window.clearInterval(id);
  }, [isSubmitting, conversationId]);

  return {
    task,
    run,
    artifacts,
    statusLabel: statusLabel(run, isSubmitting),
    loading,
    error,
    refresh,
  };
}
