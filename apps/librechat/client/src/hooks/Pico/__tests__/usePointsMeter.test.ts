import { formatPointsLabel } from '../formatPointsLabel';

describe('formatPointsLabel', () => {
  it('hides idle', () => {
    expect(formatPointsLabel('idle', null)).toBeNull();
  });

  it('shows quote and settled without token words', () => {
    expect(formatPointsLabel('quote', '0.048')).toBe('预计 0.048 积分');
    expect(formatPointsLabel('settled', '3.000')).toBe('实际 3.000 积分');
    expect(formatPointsLabel('pending', null)).toBe('未结算');
  });

  it('never mentions tokens or scale in the label', () => {
    const labels = [
      formatPointsLabel('quote', '0.048'),
      formatPointsLabel('settled', '3.000'),
      formatPointsLabel('pending', null),
    ].join(' ');
    expect(labels.toLowerCase()).not.toMatch(/token/);
    expect(labels).not.toMatch(/×|÷|1000/);
  });
});
