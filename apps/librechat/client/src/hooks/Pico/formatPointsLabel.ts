export type PointsBarPhase = 'idle' | 'quote' | 'pending' | 'settled';

export type PointsTurnRecord = {
  messageId: string;
  runId?: string | null;
  quote: string | null;
  actual: string | null;
};

/** Composer: only live 预计. Never 未结算. */
export function formatComposerQuote(live: boolean, quote: string | null): string | null {
  if (!live || !quote) {
    return null;
  }
  return `预计 ${quote} 积分`;
}

/** End of a round: 实际 when the ledger has tokens; otherwise keep 预计. Never wipe. */
export function formatTurnPointsLabel(
  turn: Pick<PointsTurnRecord, 'quote' | 'actual'> | null | undefined,
): string | null {
  if (!turn) {
    return null;
  }
  if (turn.actual) {
    return `实际 ${turn.actual} 积分`;
  }
  if (turn.quote) {
    return `预计 ${turn.quote} 积分`;
  }
  return null;
}

export function formatPointsLabel(phase: PointsBarPhase, points: string | null): string | null {
  if (phase === 'idle') {
    return null;
  }
  if (phase === 'settled' && points) {
    return `实际 ${points} 积分`;
  }
  if ((phase === 'quote' || phase === 'pending') && points) {
    return `预计 ${points} 积分`;
  }
  if (phase === 'quote') {
    return '预计 … 积分';
  }
  // pending without a number: keep empty rather than 「未结算」
  return null;
}
