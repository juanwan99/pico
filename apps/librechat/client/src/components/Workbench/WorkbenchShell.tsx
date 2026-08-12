/**
 * Shared chrome for WorkBuddy-class secondary pages (nav icon → full screen).
 */
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { PicoIcon } from '~/components/ui/pico-icons';
import { cn } from '~/utils';
import { getTaskReturnRoute } from './workbenchSession';

export default function WorkbenchShell({
  title,
  subtitle,
  children,
  actions,
  backTo,
  className,
  bare = false,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  actions?: ReactNode;
  backTo?: string;
  className?: string;
  bare?: boolean;
}) {
  const navigate = useNavigate();

  return (
    <div
      className={cn(
        'pico-wb-secondary pico-shell-bg flex h-full min-h-0 flex-col dark:bg-presentation',
        className,
      )}
      data-testid="workbench-shell"
    >
      <header className="flex min-h-14 shrink-0 items-center gap-3 border-b border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 py-2 dark:border-border-light dark:bg-surface-primary sm:px-6">
        <button
          type="button"
          onClick={() => navigate(backTo ?? getTaskReturnRoute())}
          className="inline-flex h-9 w-9 items-center justify-center rounded-xl text-[color:var(--pico-ink-2)] transition-colors hover:bg-[color:var(--pico-surface-2)] hover:text-[color:var(--pico-ink)]"
          aria-label="返回"
        >
          <PicoIcon name="back" size="sm" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[15px] font-semibold leading-5 tracking-[-0.01em] text-[color:var(--pico-ink)] dark:text-text-primary">
            {title}
          </h1>
          {subtitle ? (
            <p className="truncate text-[11px] text-[color:var(--pico-ink-3)]">{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </header>
      <div
        className={cn('min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden', bare ? '' : '')}
      >
        {children}
      </div>
    </div>
  );
}
