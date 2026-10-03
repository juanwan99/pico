import { formatTurnPointsLabel, zipRunsToAssistantMessages } from '../formatPointsLabel';

describe('formatTurnPointsLabel (#1171)', () => {
  it('pins 实际 at the end of a round', () => {
    expect(formatTurnPointsLabel({ live: '12.500', actual: '25.254' })).toBe('实际 25.254 积分');
  });

  it('counts 已用 up while the round runs', () => {
    expect(formatTurnPointsLabel({ live: '12.500', actual: null })).toBe(
      '已用 12.500 积分 · 进行中',
    );
  });

  it('shows nothing before the run has spent anything — no 预计 guess', () => {
    expect(formatTurnPointsLabel({ live: null, actual: null })).toBeNull();
    expect(formatTurnPointsLabel(null)).toBeNull();
  });

  it('never mentions tokens, scale or a guess', () => {
    const labels = [
      formatTurnPointsLabel({ live: '1.000', actual: null }),
      formatTurnPointsLabel({ live: null, actual: '2.000' }),
    ].join(' ');
    expect(labels.toLowerCase()).not.toMatch(/token/);
    expect(labels).not.toMatch(/×|÷|预计|未结算/);
  });
});

describe('zipRunsToAssistantMessages', () => {
  it('right-aligns every run, so an unsettled one does not shift later 实际', () => {
    const zipped = zipRunsToAssistantMessages(
      ['old', 'mid', 'new'],
      [
        { run_id: 'r-old', phase: 'settled', points: '0.010' },
        { run_id: 'r-mid', phase: 'pending', points: null },
        { run_id: 'r-new', phase: 'settled', points: '0.042' },
      ],
    );
    expect(zipped).toEqual([
      { messageId: 'old', runId: 'r-old', live: null, actual: '0.010' },
      { messageId: 'new', runId: 'r-new', live: null, actual: '0.042' },
    ]);
  });

  it('pins a single settled run on the latest reply after refresh', () => {
    const zipped = zipRunsToAssistantMessages(
      ['a1', 'a2', 'a3'],
      [{ run_id: 'only', phase: 'settled', points: '0.030' }],
    );
    expect(zipped).toEqual([{ messageId: 'a3', runId: 'only', live: null, actual: '0.030' }]);
  });
});
