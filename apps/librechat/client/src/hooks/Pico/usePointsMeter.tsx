import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { getPicoConversationPoints, getPicoRunPoints } from '~/data-provider/pico/api';
import {
  formatTurnPointsLabel,
  zipRunsToAssistantMessages,
  type PointsTurnRecord,
} from '~/hooks/Pico/formatPointsLabel';

export { formatTurnPointsLabel, zipRunsToAssistantMessages };
export type { PointsTurnRecord };

export type PointsMeterValue = {
  turnForMessage: (messageId?: string | null) => PointsTurnRecord | null;
};

const PointsMeterContext = createContext<PointsMeterValue | null>(null);

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled']);
const ACTIVE = new Set(['queued', 'running', 'preparing']);
/** How often 已用 refreshes while a run goes (#1171). */
export const LIVE_POINTS_MS = 3000;

/**
 * 积分 per reply. No number before the run: a long task's cost cannot be
 * known up front (#1171). While it runs the latest reply shows 已用 so far;
 * when it ends, 实际 — the number edu debits.
 */
export function PointsMeterProvider({
  children,
  runId,
  runStatus,
  latestAssistantMessageId,
  assistantMessageIds,
  conversationId,
}: {
  children: ReactNode;
  runId?: string | null;
  runStatus?: string | null;
  latestAssistantMessageId?: string | null;
  assistantMessageIds?: string[] | null;
  conversationId?: string | null;
}) {
  const [turns, setTurns] = useState<Record<string, PointsTurnRecord>>({});
  const [live, setLive] = useState<{ runId: string; points: string } | null>(null);
  const latestAssistantRef = useRef<string | null>(latestAssistantMessageId ?? null);
  latestAssistantRef.current = latestAssistantMessageId ?? null;
  const assistantIds = assistantMessageIds ?? [];
  const assistantKey = assistantIds.join('|');
  const assistantIdsRef = useRef(assistantIds);
  assistantIdsRef.current = assistantIds;

  useEffect(() => {
    const cid = (conversationId || '').trim();
    if (!cid || cid === 'new' || !assistantKey) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const view = await getPicoConversationPoints(cid);
        if (cancelled) {
          return;
        }
        const zipped = zipRunsToAssistantMessages(assistantIdsRef.current, view.turns || []);
        if (!zipped.length) {
          return;
        }
        setTurns((prev) => {
          const next = { ...prev };
          for (const row of zipped) {
            if (!next[row.messageId]?.actual) {
              next[row.messageId] = row;
            }
          }
          return next;
        });
      } catch {
        /* the footer stays empty until the ledger answers */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, assistantKey]);

  useEffect(() => {
    if (!runId || !runStatus || !ACTIVE.has(runStatus)) {
      return;
    }
    let cancelled = false;
    const rid = runId;
    const tick = async () => {
      try {
        const view = await getPicoRunPoints(rid);
        if (!cancelled && view.phase === 'live' && typeof view.points === 'string') {
          setLive({ runId: rid, points: view.points });
        }
      } catch {
        /* keep the last 已用 */
      }
    };
    void tick();
    const timer = window.setInterval(() => void tick(), LIVE_POINTS_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [runId, runStatus]);

  useEffect(() => {
    if (!runId || !runStatus || !TERMINAL.has(runStatus)) {
      return;
    }
    let cancelled = false;
    const rid = runId;
    void (async () => {
      // The llm row lands just after the terminal status; wait for 实际.
      for (let i = 0; i < 30 && !cancelled; i += 1) {
        try {
          const view = await getPicoRunPoints(rid);
          const mid = latestAssistantRef.current;
          if (!cancelled && view.phase === 'settled' && typeof view.points === 'string' && mid) {
            const actual = view.points;
            setTurns((prev) => ({
              ...prev,
              [mid]: { messageId: mid, runId: rid, live: null, actual },
            }));
            return;
          }
        } catch {
          /* retry */
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [runId, runStatus]);

  const turnForMessage = useCallback(
    (messageId?: string | null): PointsTurnRecord | null => {
      if (!messageId) {
        return null;
      }
      if (turns[messageId]) {
        return turns[messageId];
      }
      const running = Boolean(runStatus && ACTIVE.has(runStatus));
      if (messageId === latestAssistantMessageId && running && live && live.runId === runId) {
        return { messageId, runId, live: live.points, actual: null };
      }
      return null;
    },
    [turns, latestAssistantMessageId, live, runId, runStatus],
  );

  const value = useMemo<PointsMeterValue>(() => ({ turnForMessage }), [turnForMessage]);

  return <PointsMeterContext.Provider value={value}>{children}</PointsMeterContext.Provider>;
}

export function usePointsMeter(): PointsMeterValue {
  return useContext(PointsMeterContext) ?? { turnForMessage: () => null };
}
