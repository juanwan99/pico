export type PointsBarPhase = 'idle' | 'quote' | 'pending' | 'settled';

export function formatPointsLabel(phase: PointsBarPhase, points: string | null): string | null {
  if (phase === 'idle') {
    return null;
  }
  if (phase === 'quote' && points) {
    return `预计 ${points} 积分`;
  }
  if (phase === 'settled' && points) {
    return `实际 ${points} 积分`;
  }
  if (phase === 'pending' || phase === 'quote') {
    return phase === 'quote' ? '预计 … 积分' : '未结算';
  }
  return null;
}
