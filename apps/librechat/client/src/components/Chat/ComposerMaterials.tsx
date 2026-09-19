import { cn } from '~/utils';
import ArchiveFolderBar from '~/components/Chat/ArchiveFolderBar';
import SchoolMaterialsBar from '~/components/Chat/SchoolMaterialsBar';

export function ComposerMaterialsPanel({
  conversationId,
  open,
}: {
  conversationId?: string | null;
  open: boolean;
}) {
  if (!open) {
    return null;
  }
  return (
    <div
      className="mb-2 max-h-[min(40vh,20rem)] overflow-y-auto overscroll-contain max-sm:absolute max-sm:bottom-full max-sm:left-0 max-sm:right-0 max-sm:z-30 max-sm:mb-2 max-sm:max-h-[40vh] max-sm:rounded-xl max-sm:border max-sm:border-[color:var(--pico-line)] max-sm:bg-[color:var(--pico-surface)] max-sm:p-3 max-sm:shadow-[var(--pico-shadow-raised)]"
      data-testid="composer-materials-panel"
    >
      <SchoolMaterialsBar conversationId={conversationId} />
      <ArchiveFolderBar conversationId={conversationId} />
    </div>
  );
}

export function ComposerMaterialsChip({
  open,
  onToggle,
}: {
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      data-testid="composer-materials-toggle"
      aria-pressed={open}
      aria-label="学校材料与存档"
      className={cn(
        'pico-type-aux pico-hit inline-flex shrink-0 items-center rounded-lg border px-2.5 transition-colors',
        open
          ? 'border-[color:var(--pico-accent)] bg-[color:var(--pico-accent-wash)] text-[color:var(--pico-ink)]'
          : 'border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] text-[color:var(--pico-ink-2)] hover:text-[color:var(--pico-ink)]',
      )}
      onClick={onToggle}
    >
      材料
    </button>
  );
}
