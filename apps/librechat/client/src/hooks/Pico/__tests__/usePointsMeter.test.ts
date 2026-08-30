import {
  formatComposerQuote,
  formatPointsLabel,
  formatTurnPointsLabel,
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

describe('formatComposerQuote', () => {
  it('shows live 预计 only', () => {
    expect(formatComposerQuote(true, '0.018')).toBe('预计 0.018 积分');
    expect(formatComposerQuote(false, '0.018')).toBeNull();
    expect(formatComposerQuote(true, null)).toBeNull();
  });
});
