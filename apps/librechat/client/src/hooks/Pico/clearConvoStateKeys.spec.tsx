import React from 'react';
import { act, renderHook } from '@testing-library/react';
import { RecoilRoot, useRecoilValue, useSetRecoilState } from 'recoil';
import store from '~/store';

const wrapper = ({ children }: { children: React.ReactNode }) => <RecoilRoot>{children}</RecoilRoot>;

describe('useClearConvoState (pico#1328)', () => {
  it('keeps the root chat registered so anySubmittingSelector still sees it', async () => {
    const { result } = renderHook(
      () => {
        store.useCreateConversationAtom(0);
        store.useCreateConversationAtom(1);
        return {
          clear: store.useClearConvoState(),
          keys: useRecoilValue(store.conversationKeysAtom),
          setSubmitting: useSetRecoilState(store.isSubmittingFamily(0)),
          anySubmitting: useRecoilValue(store.anySubmittingSelector),
        };
      },
      { wrapper },
    );
    expect(result.current.keys).toEqual([0, 1]);

    await act(() => result.current.clear(true));
    expect(result.current.keys).toEqual([0]);

    act(() => result.current.setSubmitting(true));
    expect(result.current.anySubmitting).toBe(true);
  });

  it('drops every key on a full clear', async () => {
    const { result } = renderHook(
      () => {
        store.useCreateConversationAtom(0);
        return {
          clear: store.useClearConvoState(),
          keys: useRecoilValue(store.conversationKeysAtom),
        };
      },
      { wrapper },
    );
    await act(() => result.current.clear());
    expect(result.current.keys).toEqual([]);
  });
});
