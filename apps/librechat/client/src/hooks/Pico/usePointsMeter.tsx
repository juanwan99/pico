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
import { getPicoRunPoints, quotePicoPoints } from '~/data-provider/pico/api';
import {
  formatComposerQuote,
  formatPointsLabel,
  formatTurnPointsLabel,
  type PointsBarPhase,
  type PointsTurnRecord,
} from '~/hooks/Pico/formatPointsLabel';

export { formatComposerQuote, formatPointsLabel, formatTurnPointsLabel };
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
  isSubmitting,
}: {
  children: ReactNode;
  runId?: string | null;
  runStatus?: string | null;
  latestAssistantMessageId?: string | null;
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
    const quote = inflightQuote;
    const actual = runId ? settledByRunRef.current[runId] || null : null;
    if (!quote && !actual) {
      return;
    }
    setTurns((prev) => {
      if (prev[mid]) {
        return prev;
      }
      boundRef.current.messageId = mid;
      if (runId) {
        boundRef.current.runId = runId;
      }
      return {
        ...prev,
        [mid]: {
          messageId: mid,
          runId: runId ?? null,
          quote,
          actual,
        },
      };
    });
  }, [inflightQuote, latestAssistantMessageId, runId]);

  useEffect(() => {
    if (!runId) {
      return;
    }
    const mid = boundRef.current.messageId;
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
    if (!runId || !runStatus || !TERMINAL.has(runStatus)) {
      return;
    }
    let cancelled = false;
    const rid = runId;

    const applyActual = (points: string) => {
      settledByRunRef.current[rid] = points;
      setTurns((prev) => {
        const entry = Object.values(prev).find((t) => t.runId === rid);
        const mid = entry?.messageId || boundRef.current.messageId || latestAssistantRef.current;
        if (!mid) {
          return prev;
        }
        const cur = prev[mid];
        if (cur?.actual === points && cur.runId === rid) {
          return prev;
        }
        return {
          ...prev,
          [mid]: {
            messageId: mid,
            runId: rid,
            quote: cur?.quote ?? inflightQuoteRef.current,
            actual: points,
          },
        };
      });
      if (boundRef.current.runId === rid) {
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
          actual: null,
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
