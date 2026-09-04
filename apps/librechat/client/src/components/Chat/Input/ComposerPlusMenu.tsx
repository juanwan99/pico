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
      className="inline-flex h-8 shrink-0 items-center rounded-md border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-0"
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
              'pico-type-aux h-full rounded px-2 transition-colors',
              active
                ? 'bg-[color:var(--pico-surface-2)] font-medium text-[color:var(--pico-ink)]'
                : 'text-[color:var(--pico-ink-3)] hover:text-[color:var(--pico-ink)]',
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
        'pico-type-aux h-8 shrink-0 rounded-md border border-[color:var(--pico-line)] px-2 transition-colors',
        on
          ? 'bg-[color:var(--pico-surface-2)] font-medium text-[color:var(--pico-ink)]'
          : 'bg-[color:var(--pico-surface)] text-[color:var(--pico-ink-3)] hover:text-[color:var(--pico-ink)]',
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
