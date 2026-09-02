import { resolveLedgerConversationId } from '../picoLedgerConvo';

describe('resolveLedgerConversationId', () => {
  it('keeps a saved route id', () => {
    expect(resolveLedgerConversationId('c-real', 'c-other')).toBe('c-real');
  });

  it('uses the Recoil saved id while the route is still /c/new', () => {
    expect(resolveLedgerConversationId('new', 'c-real')).toBe('c-real');
    expect(resolveLedgerConversationId(undefined, 'c-real')).toBe('c-real');
  });

  it('does not treat pending_* as a saved id, and leaves /search alone', () => {
    expect(resolveLedgerConversationId('new', 'pending_abc')).toBe('new');
    expect(resolveLedgerConversationId('search', 'c-real')).toBe('search');
    expect(resolveLedgerConversationId('search', undefined)).toBe('search');
  });

  it('falls back to the route when nothing is saved yet', () => {
    expect(resolveLedgerConversationId('new', 'new')).toBe('new');
    expect(resolveLedgerConversationId('new', undefined)).toBe('new');
  });
});
