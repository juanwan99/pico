import { useRef } from 'react';
import type { TConversation } from 'librechat-data-provider';
import type { ExtendedFile, FileSetter } from '~/common';
import { useFileHandlingNoChatContext } from '~/hooks';
import { cn } from '~/utils';

export const PLUS_MODE_ITEMS = [
  { id: 'pico-fast', label: '快速' },
  { id: 'pico-deep', label: '深度' },
] as const;

export function ComposerModeSwitch({
  value,
  onChange,
}: {
  value: string;
  onChange: (id: string) => void;
}) {
  return (
    <div
      role="group"
      aria-label="回复深度"
      data-testid="composer-mode-switch"
      className="pico-hit inline-flex shrink-0 items-center rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-0.5"
    >
      {PLUS_MODE_ITEMS.map((item) => {
        const active = value === item.id;
        return (
          <button
            key={item.id}
            type="button"
            data-testid={`composer-plus-mode-${item.id}`}
            aria-pressed={active}
            className={cn(
              'pico-type-aux h-full rounded-md px-2.5 transition-colors',
              active
                ? 'bg-[color:var(--pico-accent-wash)] font-medium text-[color:var(--pico-ink)]'
                : 'text-[color:var(--pico-ink-2)] hover:text-[color:var(--pico-ink)]',
            )}
            onClick={() => onChange(item.id)}
          >
            {item.label}
          </button>
        );
      })}
    </div>
  );
}

/** 封存 · pico#1349 (owner 10-18): not rendered anywhere; kept for restore.
 * pico#1331「我的接口」: shown next to the 快速/深度 switch — the only
 * "model" indicator teachers see — when the teacher's own endpoint is on.
 * This turn's model fee goes to their own provider, not Pico points. */
export function ComposerMyEndpointBadge() {
  return (
    <span
      data-testid="composer-my-endpoint-badge"
      title="这次对话用你自己配的接口，模型费用由你自己的服务商收"
      className="pico-type-aux shrink-0 rounded-lg border border-[color:var(--pico-accent)] bg-[color:var(--pico-accent-wash)] px-2 py-0.5 font-medium text-[color:var(--pico-ink)]"
    >
      我的接口
    </span>
  );
}

export function ComposerPlanToggle({
  on,
  onChange,
}: {
  on: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      data-testid="composer-plan-toggle"
      aria-pressed={on}
      aria-label="先计划"
      className={cn(
        'pico-type-aux pico-hit shrink-0 rounded-lg border px-2.5 transition-colors',
        on
          ? 'border-[color:var(--pico-accent)] bg-[color:var(--pico-accent-wash)] font-medium text-[color:var(--pico-ink)]'
          : 'border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] text-[color:var(--pico-ink-2)] hover:text-[color:var(--pico-ink)]',
      )}
      onClick={() => onChange(!on)}
    >
      先计划
    </button>
  );
}

export function useComposerAttachInput({
  conversation,
  files,
  setFiles,
  setFilesLoading,
  disabled,
  onPicked,
}: {
  conversation: TConversation | null;
  files: Map<string, ExtendedFile>;
  setFiles: FileSetter;
  setFilesLoading: React.Dispatch<React.SetStateAction<boolean>>;
  disabled?: boolean;
  onPicked?: () => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const { handleFileChange, handleFiles } = useFileHandlingNoChatContext(undefined, {
    files,
    setFiles,
    setFilesLoading,
    conversation,
  });

  const openPicker = () => {
    if (!inputRef.current || disabled) {
      return;
    }
    inputRef.current.value = '';
    inputRef.current.click();
  };

  const input = (
    <input
      ref={inputRef}
      type="file"
      multiple
      className="hidden"
      data-testid="composer-plus-file-input"
      disabled={disabled}
      onChange={(event) => {
        handleFileChange(event);
        onPicked?.();
      }}
    />
  );

  return { input, openPicker, handleFiles };
}
