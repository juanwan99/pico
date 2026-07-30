/**
 * Shared chrome for WorkBuddy-class secondary pages (nav icon → full screen).
 */
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { cn } from '~/utils';

export default function WorkbenchShell({
  title,
  subtitle,
  children,
  actions,
  backTo = '/c/new',
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
      className={cn('pico-wb-secondary flex h-full min-h-0 flex-col bg-[#fafafa] dark:bg-presentation', className)}
      data-testid="workbench-shell"
    >
      <header className="flex h-11 shrink-0 items-center gap-2 border-b border-black/[0.06] bg-white px-3 dark:border-border-light dark:bg-surface-primary">
        <button
          type="button"
          onClick={() => navigate(backTo)}
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-[#3d3d3d] hover:bg-black/[0.04]"
          aria-label="返回"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">
            {title}
          </h1>
          {subtitle ? (
            <p className="truncate text-[11px] text-[#8c8c8c]">{subtitle}</p>
          ) : null}
        </div>
        {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
      </header>
      <div className={cn('min-h-0 flex-1 overflow-y-auto', bare ? '' : '')}>{children}</div>
    </div>
  );
}
