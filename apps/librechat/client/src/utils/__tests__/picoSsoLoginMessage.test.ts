import { getSsoLoginMessage } from '../getSsoLoginMessage';

describe('getSsoLoginMessage', () => {
  it('is empty when the query is missing', () => {
    expect(getSsoLoginMessage(null)).toBe('');
    expect(getSsoLoginMessage('')).toBe('');
  });

  it('tells the teacher to go back through school, not a password box', () => {
    expect(getSsoLoginMessage('expired')).toMatch(/过期/);
    expect(getSsoLoginMessage('used')).toMatch(/用过/);
    expect(getSsoLoginMessage('missing')).toMatch(/学校入口/);
    expect(getSsoLoginMessage('upstream')).toMatch(/连不上/);
    expect(getSsoLoginMessage('invalid')).toMatch(/未成功/);
    expect(getSsoLoginMessage('expired')).not.toMatch(/密码/);
  });

  it('falls back to the generic line for unknown reasons', () => {
    expect(getSsoLoginMessage('wat')).toBe(getSsoLoginMessage('invalid'));
  });
});
