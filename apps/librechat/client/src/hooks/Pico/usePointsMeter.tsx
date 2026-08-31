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
import { getPicoConversationPoints, getPicoRunPoints, quotePicoPoints } from '~/data-provider/pico/api';
import {
  formatComposerQuote,
  formatPointsLabel,
  formatTurnPointsLabel,
  migrateTurnMessageId,
  zipRunsToAssistantMessages,
  type PointsBarPhase,
  type PointsTurnRecord,
} from '~/hooks/Pico/formatPointsLabel';

export {
  formatComposerQuote,
  formatPointsLabel,
  formatTurnPointsLabel,
  migrateTurnMessageId,
  zipRunsToAssistantMessages,
};
export type { PointsBarPhase, PointsTurnRecord };

export type PointsMeterValue = {
  phase: PointsBarPhase;
  points: string | null;
  quoteFromChars: (n: number) => void;
  turnForMessage: (messageId?: string | null) => PointsTurnRecord | null;
  composerLive: boolean;
};

const PointsMeterContext = createContext<PointsMeterValue | null>(null);

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled']);
const ACTIVE = new Set(['queued', 'running', 'preparing']);

export function PointsMeterProvider({
  children,
  runId,
  runStatus,
  latestAssistantMessageId,
  assistantMessageIds,
  conversationId,
  isSubmitting,
}: {
  children: ReactNode;
  runId?: string | null;
  runStatus?: string | null;
  latestAssistantMessageId?: string | null;
  assistantMessageIds?: string[] | null;
  conversationId?: string | null;
  isSubmitting?: boolean;
}) {
  const [inflightQuote, setInflightQuote] = useState<string | null>(null);
  const [turns, setTurns] = useState<Record<string, PointsTurnRecord>>({});
  const boundRef = useRef<{ runId: string | null; messageId: string | null }>({
    runId: null,
    messageId: null,
  });
  const inflightQuoteRef = useRef<string | null>(null);
  inflightQuoteRef.current = inflightQuote;
  const latestAssistantRef = useRef<string | null>(latestAssistantMessageId ?? null);
  latestAssistantRef.current = latestAssistantMessageId ?? null;
  const settledByRunRef = useRef<Record<string, string>>({});
  const assistantIds = assistantMessageIds ?? [];
  const assistantKey = assistantIds.join('|');
  const assistantIdsRef = useRef(assistantIds);
  assistantIdsRef.current = assistantIds;

  const quoteFromChars = useCallback((n: number) => {
    boundRef.current = { runId: null, messageId: null };
    void quotePicoPoints(n)
      .then((view) => {
        setInflightQuote(typeof view.points === 'string' ? view.points : null);
      })
      .catch(() => {
        setInflightQuote(null);
      });
  }, []);

  useEffect(() => {
    const mid = latestAssistantMessageId;
    if (!mid) {
      return;
    }
    setTurns((prev) => {
      const moved = migrateTurnMessageId(prev, boundRef.current.messageId, mid);
      if (moved[mid]) {
        return moved === prev ? prev : moved;
      }
      const quote = inflightQuote;
      const actual = runId ? settledByRunRef.current[runId] || null : null;
      if (!quote && !actual) {
        return moved;
      }
      return {
        ...moved,
        [mid]: {
          messageId: mid,
          runId: runId ?? null,
          quote,
          actual,
        },
      };
    });
    boundRef.current.messageId = mid;
    if (runId) {
      boundRef.current.runId = runId;
    }
  }, [inflightQuote, latestAssistantMessageId, runId]);

  useEffect(() => {
    if (!runId) {
      return;
    }
    const mid = boundRef.current.messageId || latestAssistantRef.current;
    if (!mid) {
      return;
    }
    boundRef.current.runId = runId;
    const actual = settledByRunRef.current[runId] || null;
    setTurns((prev) => {
      const cur = prev[mid];
      if (!cur) {
        return prev;
      }
      if (cur.runId === runId && (!actual || cur.actual === actual)) {
        return prev;
      }
      return { ...prev, [mid]: { ...cur, runId, actual: actual || cur.actual } };
    });
  }, [runId]);

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
          let changed = false;
          const next = { ...prev };
          for (const row of zipped) {
            if (row.actual) {
              settledByRunRef.current[row.runId || ''] = row.actual;
            }
            const cur = next[row.messageId];
            if (cur?.actual) {
              continue;
            }
            changed = true;
            next[row.messageId] = {
              messageId: row.messageId,
              runId: row.runId ?? cur?.runId ?? null,
              quote: cur?.quote ?? null,
              actual: row.actual,
            };
          }
          return changed ? next : prev;
        });
      } catch {
        /* keep 预计 until tokens land */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [conversationId, assistantKey]);

  useEffect(() => {
    if (!runId || !runStatus || !TERMINAL.has(runStatus)) {
      return;
    }
    let cancelled = false;
    const rid = runId;

    const applyActual = (points: string) => {
      settledByRunRef.current[rid] = points;
      const preferredMid = latestAssistantRef.current || boundRef.current.messageId;
      setTurns((prev) => {
        const entry = Object.values(prev).find((t) => t.runId === rid);
        const mid = preferredMid || entry?.messageId;
        if (!mid) {
          return prev;
        }
        const cur = prev[mid] || (entry ? prev[entry.messageId] : undefined);
        if (cur?.actual === points && cur.runId === rid && prev[mid]) {
          return prev;
        }
        const next = { ...prev };
        if (entry && entry.messageId !== mid) {
          delete next[entry.messageId];
        }
        next[mid] = {
          messageId: mid,
          runId: rid,
          quote: cur?.quote ?? inflightQuoteRef.current,
          actual: points,
        };
        return next;
      });
      const shouldClearQuote =
        !boundRef.current.runId || boundRef.current.runId === rid;
      if (preferredMid) {
        boundRef.current.messageId = preferredMid;
      }
      boundRef.current.runId = rid;
      if (shouldClearQuote) {
        setInflightQuote(null);
      }
    };

    const tick = async () => {
      const view = await getPicoRunPoints(rid);
      if (cancelled) {
        return false;
      }
      if (view.phase === 'settled' && typeof view.points === 'string') {
        applyActual(view.points);
        return true;
      }
      return false;
    };

    void (async () => {
      for (let i = 0; i < 30; i += 1) {
        try {
          if (await tick()) {
            return;
          }
        } catch {
          /* keep 预计 on that turn until tokens land */
        }
        if (cancelled) {
          return;
        }
        await new Promise((r) => setTimeout(r, 1000));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, runStatus]);

  const composerLive = Boolean(
    inflightQuote &&
      (!latestAssistantMessageId ||
        Boolean(isSubmitting) ||
        (runStatus != null && ACTIVE.has(runStatus))),
  );

  const turnForMessage = useCallback(
    (messageId?: string | null): PointsTurnRecord | null => {
      if (!messageId) {
        return null;
      }
      if (turns[messageId]) {
        return turns[messageId];
      }
      if (messageId === latestAssistantMessageId && inflightQuote) {
        return {
          messageId,
          runId: runId ?? null,
          quote: inflightQuote,
          actual: runId ? settledByRunRef.current[runId] || null : null,
        };
      }
      return null;
    },
    [turns, latestAssistantMessageId, inflightQuote, runId],
  );

  const value = useMemo<PointsMeterValue>(
    () => ({
      phase: composerLive ? 'quote' : 'idle',
      points: composerLive ? inflightQuote : null,
      quoteFromChars,
      turnForMessage,
      composerLive,
    }),
    [composerLive, inflightQuote, quoteFromChars, turnForMessage],
  );

  return <PointsMeterContext.Provider value={value}>{children}</PointsMeterContext.Provider>;
}

export function usePointsMeter(): PointsMeterValue {
  return (
    useContext(PointsMeterContext) ?? {
      phase: 'idle',
      points: null,
      quoteFromChars: () => undefined,
      turnForMessage: () => null,
      composerLive: false,
    }
  );
}
