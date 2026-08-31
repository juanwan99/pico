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

export function migrateTurnMessageId(
  turns: Record<string, PointsTurnRecord>,
  fromId: string | null | undefined,
  toId: string | null | undefined,
): Record<string, PointsTurnRecord> {
  if (!toId || fromId === toId) {
    return turns;
  }
  if (turns[toId]) {
    return turns;
  }
  if (fromId && turns[fromId]) {
    const next = { ...turns, [toId]: { ...turns[fromId], messageId: toId } };
    delete next[fromId];
    return next;
  }
  return turns;
}

export function zipRunsToAssistantMessages(
  messageIds: string[],
  runs: Array<{ run_id?: string | null; points?: string | null; phase?: string | null }>,
): PointsTurnRecord[] {
  const settled = runs.filter((row) => row.phase === 'settled' && row.points && row.run_id);
  const n = Math.min(messageIds.length, settled.length);
  if (n <= 0) {
    return [];
  }
  const ids = messageIds.slice(messageIds.length - n);
  const slice = settled.slice(settled.length - n);
  return ids.map((id, i) => ({
    messageId: id,
    runId: slice[i].run_id ?? null,
    quote: null,
    actual: slice[i].points ?? null,
  }));
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
