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
import {
  getPicoRunPoints,
  quotePicoPoints,
} from '~/data-provider/pico/api';
import {
  formatPointsLabel,
  type PointsBarPhase,
} from '~/hooks/Pico/formatPointsLabel';

export { formatPointsLabel };
export type { PointsBarPhase };

export type PointsMeterValue = {
  phase: PointsBarPhase;
  points: string | null;
  quoteFromChars: (n: number) => void;
};

const PointsMeterContext = createContext<PointsMeterValue | null>(null);

const TERMINAL = new Set(['succeeded', 'failed', 'cancelled']);

export function PointsMeterProvider({
  children,
  runId,
  runStatus,
}: {
  children: ReactNode;
  runId?: string | null;
  runStatus?: string | null;
}) {
  const [phase, setPhase] = useState<PointsBarPhase>('idle');
  const [points, setPoints] = useState<string | null>(null);
  const pollRef = useRef(0);

  const quoteFromChars = useCallback((n: number) => {
    void quotePicoPoints(n)
      .then((view) => {
        setPhase('quote');
        setPoints(typeof view.points === 'string' ? view.points : null);
      })
      .catch(() => {
        setPhase('quote');
        setPoints(null);
      });
  }, []);

  useEffect(() => {
    if (!runId || !runStatus || !TERMINAL.has(runStatus)) {
      return;
    }
    let cancelled = false;
    pollRef.current += 1;
    const ticket = pollRef.current;
    setPhase((prev) => (prev === 'idle' ? prev : 'pending'));

    const tick = async () => {
      try {
        const view = await getPicoRunPoints(runId);
        if (cancelled || ticket !== pollRef.current) {
          return false;
        }
        if (view.phase === 'settled' && typeof view.points === 'string') {
          setPhase('settled');
          setPoints(view.points);
          return true;
        }
        setPhase('pending');
        setPoints(null);
        return false;
      } catch {
        return false;
      }
    };

    void (async () => {
      for (let i = 0; i < 8; i += 1) {
        const done = await tick();
        if (done || cancelled) {
          return;
        }
        await new Promise((r) => setTimeout(r, 800));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [runId, runStatus]);

  const value = useMemo(
    () => ({ phase, points, quoteFromChars }),
    [phase, points, quoteFromChars],
  );

  return <PointsMeterContext.Provider value={value}>{children}</PointsMeterContext.Provider>;
}

export function usePointsMeter(): PointsMeterValue {
  return (
    useContext(PointsMeterContext) ?? {
      phase: 'idle',
      points: null,
      quoteFromChars: () => undefined,
    }
  );
}
