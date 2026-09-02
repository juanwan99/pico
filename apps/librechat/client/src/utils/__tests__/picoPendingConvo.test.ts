import { ensurePendingConvoId, markPendingRebind, peekPendingConvoId } from '~/utils/picoPendingConvo';

describe('picoPendingConvo', () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it('mints one pending id and reuses it', () => {
    const first = ensurePendingConvoId();
    expect(first.startsWith('pending_')).toBe(true);
    expect(ensurePendingConvoId()).toBe(first);
    expect(peekPendingConvoId()).toBe(first);
  });

  it('hands the draft to rebind when the real conversation id arrives', () => {
    const pending = ensurePendingConvoId();
    markPendingRebind('c-real');
    expect(peekPendingConvoId()).toBeNull();
    expect(sessionStorage.getItem('pico:rebindFrom')).toBe(pending);
    expect(sessionStorage.getItem('pico:rebindTo')).toBe('c-real');
  });
});
