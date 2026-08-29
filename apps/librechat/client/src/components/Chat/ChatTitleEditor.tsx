/**
 * Header conversation title: click to rename. Auto-name is first-user-turn snippet.
 */
import { useEffect, useState } from 'react';
import { useUpdateConversationMutation } from '~/data-provider';
import { isUnnamedConvoTitle } from '~/utils/picoConvoTitle';
import { cn } from '~/utils';

export default function ChatTitleEditor({
  conversationId,
  title,
}: {
  conversationId?: string | null;
  title?: string | null;
}) {
  const canEdit = Boolean(conversationId && conversationId !== 'new');
  const display = isUnnamedConvoTitle(title) ? '新对话' : (title as string);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(display);
  const updateConvoMutation = useUpdateConversationMutation(conversationId ?? '');

  useEffect(() => {
    if (!editing) {
      setDraft(isUnnamedConvoTitle(title) ? '新对话' : (title ?? ''));
    }
  }, [title, editing]);

  if (!canEdit) {
    return null;
  }

  const save = async () => {
    const next = draft.trim();
    setEditing(false);
    if (!next || next === title) {
      return;
    }
    try {
      await updateConvoMutation.mutateAsync({
        conversationId: conversationId as string,
        title: next,
      });
    } catch {
      setDraft(display);
    }
  };

  if (editing) {
    return (
      <form
        className="min-w-0 flex-1"
        data-testid="chat-title-form"
        onSubmit={(event) => {
          event.preventDefault();
          void save();
        }}
      >
        <input
          autoFocus
          data-testid="chat-title-input"
          aria-label="对话标题"
          className="pico-type-body w-full max-w-[min(28rem,70vw)] rounded-md border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-2 py-1 font-medium text-[color:var(--pico-ink)] outline-none"
          value={draft}
          maxLength={100}
          onChange={(event) => setDraft(event.target.value)}
          onBlur={() => void save()}
          onKeyDown={(event) => {
            if (event.key === 'Escape') {
              event.preventDefault();
              setDraft(display);
              setEditing(false);
            }
          }}
        />
      </form>
    );
  }

  return (
    <button
      type="button"
      data-testid="chat-title"
      title="点击修改标题"
      aria-label={`对话标题 ${display}，点击修改`}
      className={cn(
        'pico-type-body min-w-0 max-w-[min(28rem,70vw)] truncate rounded-md px-2 py-1 text-left font-semibold text-[color:var(--pico-ink)] hover:bg-black/[0.04]',
        isUnnamedConvoTitle(title) && 'text-[color:var(--pico-ink-3)]',
      )}
      onClick={() => {
        setDraft(isUnnamedConvoTitle(title) ? '' : (title ?? ''));
        setEditing(true);
      }}
    >
      {display}
    </button>
  );
}
