/**
 * Shared map: conversationId → teacher-facing latest run label from Pico ledger.
 * One listPicoTasks poll for the whole sidebar (no per-row N+1).
 */
import { useCallback, useEffect, useState } from 'react';
import {
  labelForLatestRun,
  listPicoTasks,
  type PicoTask,
} from '~/data-provider/pico/api';

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
export function buildConversationStatusMap(tasks: PicoTask[] | null | undefined): ConversationStatusMap {
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
  statusByConversationId: ConversationStatusMap;
  refresh: () => void;
} {
  const [statusByConversationId, setStatusByConversationId] = useState<ConversationStatusMap>(
    {},
  );
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) {
      return;
    }
    let cancelled = false;
    const load = async () => {
      try {
        const { tasks } = await listPicoTasks();
        if (cancelled) {
          return;
        }
        setStatusByConversationId(buildConversationStatusMap(tasks));
      } catch {
        /* keep last good map; sidebar must not break on ledger blip */
      }
    };
    void load();
    const id = window.setInterval(() => void load(), POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [enabled, tick]);

  return { statusByConversationId, refresh };
}
