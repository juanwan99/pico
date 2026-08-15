import { useRef } from 'react';
import type { TConversation } from 'librechat-data-provider';
import type { ExtendedFile, FileSetter } from '~/common';
import { useFileHandlingNoChatContext } from '~/hooks';
import { cn } from '~/utils';

export const PLUS_MODE_ITEMS = [
  { id: 'pico-fast', label: '快速' },
  { id: 'pico-deep', label: '深度' },
] as const;

export function ComposerPlusMenu({ children }: { children: React.ReactNode }) {
  return (
    <div
      data-testid="composer-plus-menu"
      className="pico-card absolute bottom-full left-0 z-50 mb-2 w-52 overflow-hidden py-1 shadow-[var(--pico-shadow-raised)]"
    >
      {children}
    </div>
  );
}

export function ComposerPlusItem({
  children,
  onClick,
  active,
  testId,
}: {
  children: React.ReactNode;
  onClick: () => void;
  active?: boolean;
  testId?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testId}
      className={cn(
        'pico-type-sidebar flex w-full px-3 py-2 text-left hover:bg-[color:var(--pico-surface-2)]',
        active && 'font-medium text-[color:var(--pico-ink)]',
      )}
      onClick={onClick}
    >
      {children}
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
  const { handleFileChange } = useFileHandlingNoChatContext(undefined, {
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

  return { input, openPicker };
}

export function ComposerPlusAttach({
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
  const { input, openPicker } = useComposerAttachInput({
    conversation,
    files,
    setFiles,
    setFilesLoading,
    disabled,
    onPicked,
  });

  return (
    <>
      {input}
      <ComposerPlusItem testId="composer-plus-attach" onClick={openPicker}>
        上传附件
      </ComposerPlusItem>
    </>
  );
}
