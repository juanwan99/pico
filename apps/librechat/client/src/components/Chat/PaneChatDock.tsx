/**
 * Small chat dock under the full-screen sandbox (#1226): the teacher works the
 * page and talks to the AI without leaving full screen. Sends through the same
 * LibreChat `useSubmitMessage` path as conversation starters; stop = the task
 * bar's「停止任务」. Shows the AI's latest reply, not the whole thread.
 */
import { useState, type ReactNode } from 'react';
import type { TMessage } from 'librechat-data-provider';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useSubmitMessage } from '~/hooks';
import { useChatContext } from '~/Providers';
import { getAllContentText } from '~/utils/messages';
import { humanizeChatErrorText } from '../Messages/Content/Error';

export function latestReplyText(messages?: TMessage[] | null): string {
  const list = messages ?? [];
  for (let i = list.length - 1; i >= 0; i -= 1) {
    const msg = list[i];
    if (msg && !msg.isCreatedByUser) {
      const text = getAllContentText(msg).trim();
      // A failed turn reads the same as the main bubble (「这次没完成…」): either
      // the message is flagged, or it carries an error part (Part.tsx).
      const part = (msg.content ?? []).find((c) => c?.type === 'error') as
        | { error?: string; text?: string | { value?: string } }
        | undefined;
      if (!msg.error && !part) {
        return text;
      }
      const partText =
        part?.error ?? (typeof part?.text === 'string' ? part.text : part?.text?.value) ?? '';
      return humanizeChatErrorText(text || partText);
    }
  }
  return '';
}

export default function PaneChatDock({
  messages,
  processHint,
  canStop,
  stopping,
  onStop,
  askBar,
}: {
  messages?: TMessage[] | null;
  processHint?: string | null;
  canStop: boolean;
  stopping?: boolean;
  onStop: () => void;
  /** The AI's pending question (PicoAskBar), answerable from full screen. */
  askBar?: ReactNode;
}) {
  const { isSubmitting } = useChatContext();
  const { submitMessage } = useSubmitMessage();
  const [text, setText] = useState('');
  const reply = latestReplyText(messages);
  const busy = isSubmitting || canStop;

  const send = () => {
    const value = text.trim();
    if (!value || isSubmitting) {
      return;
    }
    if (submitMessage({ text: value }) !== false) {
      setText('');
    }
  };

  return (
    <div
      className="shrink-0 border-t border-black/[0.08] bg-[#fafafa] px-3 py-2 dark:border-border-light dark:bg-[color:var(--pico-surface-2)]"
      data-testid="pane-chat-dock"
    >
      <div className="mx-auto w-full max-w-[797px] space-y-1.5">
        {askBar}
        {busy && processHint ? (
          <div className="text-[12px] text-[#3b6fd9]" data-testid="pane-chat-dock-status">
            {processHint}
          </div>
        ) : null}
        {reply ? (
          <div
            className="max-h-[72px] overflow-y-auto whitespace-pre-wrap text-[13px] leading-5 text-[#3d3d3d] dark:text-text-secondary"
            data-testid="pane-chat-dock-reply"
          >
            {reply}
          </div>
        ) : null}
        <form
          className="flex items-end gap-2 rounded-xl border border-black/[0.08] bg-white px-2 py-1.5 dark:border-border-light dark:bg-surface-secondary"
          onSubmit={(ev) => {
            ev.preventDefault();
            send();
          }}
        >
          <textarea
            rows={1}
            value={text}
            placeholder="边看网页边跟 AI 说…"
            aria-label="对 AI 说"
            data-testid="pane-chat-dock-input"
            className="max-h-24 min-h-[28px] flex-1 resize-none bg-transparent px-1 py-1 text-[13px] outline-none"
            onChange={(ev) => setText(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === 'Enter' && !ev.shiftKey && !ev.nativeEvent.isComposing) {
                ev.preventDefault();
                send();
              }
            }}
          />
          {busy ? (
            <button
              type="button"
              className="inline-flex h-8 shrink-0 items-center gap-1 rounded-lg border border-black/[0.1] px-2.5 text-[12px] hover:bg-black/[0.04] disabled:opacity-50"
              data-testid="pane-chat-dock-stop"
              disabled={stopping}
              onClick={onStop}
            >
              {stopping ? '停止中' : '停止'}
            </button>
          ) : null}
          <button
            type="submit"
            aria-label="发送"
            className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[#1a1a1a] text-white disabled:opacity-40"
            data-testid="pane-chat-dock-send"
            disabled={!text.trim() || isSubmitting}
          >
            <PicoIcon name="arrow-up" size="sm" />
          </button>
        </form>
      </div>
    </div>
  );
}
