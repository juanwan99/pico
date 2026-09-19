/**
 * Shared map: conversationId → teacher-facing latest run label from Pico ledger.
 * One listPicoTasks poll for the whole sidebar (no per-row N+1).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { labelForLatestRun, listPicoTasks, type PicoTask } from '~/data-provider/pico/api';

export type ConversationStatusMap = Record<string, string>;

function taskSortTime(task: PicoTask): number {
  const raw = task.latest_run?.ended_at || task.latest_run?.started_at || task.created_at || '';
  const n = Date.parse(raw);
  return Number.isNaN(n) ? 0 : n;
}

/** Pure: tasks → conversationId → label of the newest run, not the worst status. */
export function buildConversationStatusMap(
  tasks: PicoTask[] | null | undefined,
): ConversationStatusMap {
  const next: ConversationStatusMap = {};
  const seenAt: Record<string, number> = {};
  for (const task of tasks || []) {
    const label = labelForLatestRun(task.latest_run);
    if (!label || !task.conversation_id) {
      continue;
    }
    const ts = taskSortTime(task);
    const prevTs = seenAt[task.conversation_id];
    if (prevTs === undefined || ts > prevTs) {
      next[task.conversation_id] = label;
      seenAt[task.conversation_id] = ts;
    }
  }
  return next;
}

const POLL_MS = 20_000;

export function usePicoConversationStatusMap(enabled = true): {
  tasks: PicoTask[];
  statusByConversationId: ConversationStatusMap;
  loading: boolean;
  error: string | null;
  refresh: () => void;
} {
  const [tasks, setTasks] = useState<PicoTask[]>([]);
  const [statusByConversationId, setStatusByConversationId] = useState<ConversationStatusMap>({});
  const [loading, setLoading] = useState(enabled);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);
  const loadedRef = useRef(false);
  const refresh = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    const load = async () => {
      if (!loadedRef.current) {
        setLoading(true);
      }
      try {
        const { tasks } = await listPicoTasks();
        if (cancelled) {
          return;
        }
        setTasks(tasks || []);
        setStatusByConversationId(buildConversationStatusMap(tasks));
        loadedRef.current = true;
        setError(null);
      } catch {
        if (!cancelled) {
          // Keep the last good rows/map; never surface fetch internals in the sidebar.
          setError('任务历史暂不可用，请稍后重试');
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [enabled, tick]);

  return { tasks, statusByConversationId, loading, error, refresh };
}
