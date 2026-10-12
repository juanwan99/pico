/**
 * 「让 AI 接着做」(#1238): the AI stopped on a step that is the teacher's
 * (password, slider). Once done on the pane, one click says so — the same
 * `useSubmitMessage` path as the chat box, so it lands in the ledger as the
 * teacher's message. ChatView keys it by run id: a new turn starts fresh.
 * Sits at the bottom: the top of a login page is where the teacher's fields are.
 */
import { useState } from 'react';
import { useSubmitMessage } from '~/hooks';
import { useChatContext } from '~/Providers';

export const HAND_BACK_TEXT = '我在右边画面做好了，请接着做。';

export default function PaneHandBack() {
  const { isSubmitting } = useChatContext();
  const { submitMessage } = useSubmitMessage();
  const [sent, setSent] = useState(false);
  if (sent) {
    return null;
  }
  return (
    <div
      className="absolute bottom-3 left-1/2 z-20 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-[#1a1a1a]/90 py-1 pl-3 pr-1 text-[12px] text-white shadow-md"
      data-testid="sandbox-continue-bar"
      role="status"
    >
      <span>做好了就点</span>
      <button
        type="button"
        className="rounded-full bg-white px-2.5 py-0.5 text-[12px] font-medium text-[#1a1a1a] disabled:opacity-60"
        data-testid="sandbox-continue"
        disabled={isSubmitting}
        onClick={() => {
          if (submitMessage({ text: HAND_BACK_TEXT }) !== false) {
            setSent(true);
          }
        }}
      >
        让 AI 接着做
      </button>
    </div>
  );
}
