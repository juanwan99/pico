import {
  consumePendingModel,
  getPicoModelMode,
  getPicoPlanOn,
  normalizePicoModelMode,
  patchConversationModel,
  patchConversationPlan,
  queuePendingModel,
  setPicoModelMode,
  setPicoPlanOn,
} from '../picoModelPref';

describe('picoModelPref dual-mode (#637 React #185)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('maps reasoner to pico-deep before the deepseek catch-all', () => {
    expect(normalizePicoModelMode('pico-deep')).toBe('pico-deep');
    expect(normalizePicoModelMode('Pico 深度')).toBe('pico-deep');
    expect(normalizePicoModelMode('deepseek-reasoner')).toBe('pico-deep');
    expect(normalizePicoModelMode('deepseek-v4-flash')).toBe('pico-fast');
    expect(normalizePicoModelMode('pico-fast')).toBe('pico-fast');
  });

  it('setPicoModelMode does not re-arm PENDING (that looped Landing consume)', () => {
    setPicoModelMode('pico-deep');
    expect(getPicoModelMode()).toBe('pico-deep');
    expect(sessionStorage.getItem('pico:pendingModel')).toBeNull();
    expect(consumePendingModel()).toBeNull();
  });

  it('queuePendingModel is the hub handoff; consume is one-shot', () => {
    queuePendingModel('pico-deep');
    expect(sessionStorage.getItem('pico:pendingModel')).toBe('pico-deep');
    expect(consumePendingModel()).toBe('pico-deep');
    expect(consumePendingModel()).toBeNull();
    setPicoModelMode('pico-deep');
    expect(consumePendingModel()).toBeNull();
  });

  it('patchConversationModel keeps identity when the lane is unchanged', () => {
    const prev = { conversationId: 'new', endpoint: 'openAI', model: 'pico-deep' };
    expect(patchConversationModel(prev, 'pico-deep')).toBe(prev);
    const next = patchConversationModel(prev, 'pico-fast');
    expect(next).not.toBe(prev);
    expect(next?.model).toBe('pico-fast');
  });

  it('plan toggle is off by default and patches pico_plan without a new identity when unchanged', () => {
    expect(getPicoPlanOn()).toBe(false);
    setPicoPlanOn(true);
    expect(getPicoPlanOn()).toBe(true);
    const prev = { conversationId: 'new', pico_plan: true };
    expect(patchConversationPlan(prev, true)).toBe(prev);
    const next = patchConversationPlan(prev, false);
    expect(next).not.toBe(prev);
    expect(next?.pico_plan).toBe(false);
  });
});
