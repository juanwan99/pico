import {
  formatComposerQuote,
  formatPointsLabel,
  formatTurnPointsLabel,
  migrateTurnMessageId,
  zipRunsToAssistantMessages,
} from '../formatPointsLabel';

describe('formatPointsLabel', () => {
  it('hides idle', () => {
    expect(formatPointsLabel('idle', null)).toBeNull();
  });

  it('shows quote and settled without token words', () => {
    expect(formatPointsLabel('quote', '0.048')).toBe('预计 0.048 积分');
    expect(formatPointsLabel('settled', '3.000')).toBe('实际 3.000 积分');
  });

  it('keeps 预计 while pending instead of 未结算', () => {
    expect(formatPointsLabel('pending', '0.018')).toBe('预计 0.018 积分');
    expect(formatPointsLabel('pending', null)).toBeNull();
  });

  it('never mentions tokens or scale in the label', () => {
    const labels = [
      formatPointsLabel('quote', '0.048'),
      formatPointsLabel('settled', '3.000'),
      formatPointsLabel('pending', '0.018'),
    ].join(' ');
    expect(labels.toLowerCase()).not.toMatch(/token/);
    expect(labels).not.toMatch(/×|÷|1000|未结算/);
  });
});

describe('formatTurnPointsLabel', () => {
  it('pins 实际 at the end of a round when tokens landed', () => {
    expect(formatTurnPointsLabel({ quote: '0.018', actual: '0.042' })).toBe('实际 0.042 积分');
  });

  it('keeps 预计 on that round until 实际 arrives', () => {
    expect(formatTurnPointsLabel({ quote: '0.018', actual: null })).toBe('预计 0.018 积分');
  });

  it('does not invent a wipe/empty 未结算 state', () => {
    expect(formatTurnPointsLabel({ quote: null, actual: null })).toBeNull();
    expect(formatTurnPointsLabel(null)).toBeNull();
  });
});

describe('migrateTurnMessageId', () => {
  it('moves a bound turn onto the real message id', () => {
    const next = migrateTurnMessageId(
      { temp: { messageId: 'temp', runId: 'r1', quote: '0.030', actual: '0.042' } },
      'temp',
      'real',
    );
    expect(next.real).toEqual({
      messageId: 'real',
      runId: 'r1',
      quote: '0.030',
      actual: '0.042',
    });
    expect(next.temp).toBeUndefined();
  });

  it('does not wipe an already-bound real id', () => {
    const prev = {
      temp: { messageId: 'temp', quote: '0.030', actual: null },
      real: { messageId: 'real', quote: '0.030', actual: '0.042' },
    };
    expect(migrateTurnMessageId(prev, 'temp', 'real')).toBe(prev);
  });
});

describe('zipRunsToAssistantMessages', () => {
  it('right-aligns settled runs onto assistant messages', () => {
    const zipped = zipRunsToAssistantMessages(
      ['old', 'mid', 'new'],
      [
        { run_id: 'r-old', phase: 'pending', points: null },
        { run_id: 'r-mid', phase: 'settled', points: '0.018' },
        { run_id: 'r-new', phase: 'settled', points: '0.042' },
      ],
    );
    expect(zipped).toEqual([
      { messageId: 'mid', runId: 'r-mid', quote: null, actual: '0.018' },
      { messageId: 'new', runId: 'r-new', quote: null, actual: '0.042' },
    ]);
  });

  it('pins a single settled run on the latest reply after refresh', () => {
    const zipped = zipRunsToAssistantMessages(
      ['a1', 'a2', 'a3'],
      [{ run_id: 'only', phase: 'settled', points: '0.030' }],
    );
    expect(zipped).toEqual([
      { messageId: 'a3', runId: 'only', quote: null, actual: '0.030' },
    ]);
  });
});

describe('formatComposerQuote', () => {
  it('shows live 预计 only', () => {
    expect(formatComposerQuote(true, '0.018')).toBe('预计 0.018 积分');
    expect(formatComposerQuote(false, '0.018')).toBeNull();
    expect(formatComposerQuote(true, null)).toBeNull();
  });
});
