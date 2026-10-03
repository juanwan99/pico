export type PointsTurnRecord = {
  messageId: string;
  runId?: string | null;
  /** 已用 so far while the run goes (#1171). */
  live: string | null;
  actual: string | null;
};

/** End of a round: 实际. While it runs: 已用 so far. No guess before the run (#1171). */
export function formatTurnPointsLabel(
  turn: Pick<PointsTurnRecord, 'live' | 'actual'> | null | undefined,
): string | null {
  if (!turn) {
    return null;
  }
  if (turn.actual) {
    return `实际 ${turn.actual} 积分`;
  }
  if (turn.live) {
    return `已用 ${turn.live} 积分 · 进行中`;
  }
  return null;
}

/**
 * Right-align the conversation's runs onto its assistant replies. Every run
 * takes a slot, settled or not, so one unsettled run does not shift the 实际
 * of every later reply onto the one before it (#1171).
 */
export function zipRunsToAssistantMessages(
  messageIds: string[],
  runs: Array<{ run_id?: string | null; points?: string | null; phase?: string | null }>,
): PointsTurnRecord[] {
  const withId = runs.filter((row) => row.run_id);
  const n = Math.min(messageIds.length, withId.length);
  if (n <= 0) {
    return [];
  }
  const ids = messageIds.slice(messageIds.length - n);
  const slice = withId.slice(withId.length - n);
  return ids
    .map((id, i) => ({
      messageId: id,
      runId: slice[i].run_id ?? null,
      live: null,
      actual: slice[i].phase === 'settled' ? (slice[i].points ?? null) : null,
    }))
    .filter((row) => row.actual);
}
