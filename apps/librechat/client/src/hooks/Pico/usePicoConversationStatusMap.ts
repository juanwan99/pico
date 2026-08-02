/**
 * Shared map: conversationId → teacher-facing latest run label from Pico ledger.
 * One listPicoTasks poll for the whole sidebar (no per-row N+1).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { labelForLatestRun, listPicoTasks, type PicoTask } from '~/data-provider/pico/api';

export type ConversationStatusMap = Record<string, string>;

function statusRank(value: string): number {
  if (value === '进行中' || value === '停止中') {
    return 3;
  }
  if (value === '失败') {
    return 2;
  }
  if (value === '已停止') {
    return 1;
  }
  return 0;
}

/** Pure: tasks → conversationId → best teacher label. */
export function buildConversationStatusMap(
  tasks: PicoTask[] | null | undefined,
): ConversationStatusMap {
  const next: ConversationStatusMap = {};
  for (const task of tasks || []) {
    const label = labelForLatestRun(task.latest_run);
    if (!label || !task.conversation_id) {
      continue;
    }
    const prev = next[task.conversation_id];
    if (!prev || statusRank(label) >= statusRank(prev)) {
      next[task.conversation_id] = label;
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
