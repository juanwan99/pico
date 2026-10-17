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
/** While a run is live the row must flip to 已完成 within 2 s of its end (pico#1328). */
const LIVE_POLL_MS = 1_500;
const LIVE_STATUSES = new Set(['queued', 'preparing', 'running']);

/** Pure: next poll delay — fast only while some run is live and the page is visible. */
export function nextPollMs(tasks: PicoTask[] | null | undefined, hidden: boolean): number {
  const live = (tasks || []).some((t) => LIVE_STATUSES.has(t.latest_run?.status ?? ''));
  return live && !hidden ? LIVE_POLL_MS : POLL_MS;
}

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
    let timer: number | undefined;
    let latest: PicoTask[] = [];
    const schedule = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => void load(), nextPollMs(latest, document.hidden));
    };
    const load = async () => {
      if (!loadedRef.current) {
        setLoading(true);
      }
      try {
        const { tasks } = await listPicoTasks();
        if (cancelled) {
          return;
        }
        latest = tasks || [];
        setTasks(latest);
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
          schedule();
        }
      }
    };
    // Back from a background tab: pick up runs that ended meanwhile now, not in 20 s.
    const onVisible = () => {
      if (!document.hidden) {
        void load();
      }
    };
    void load();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [enabled, tick]);

  return { tasks, statusByConversationId, loading, error, refresh };
}
