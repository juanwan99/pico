import React from 'react';
import { cn } from '~/utils';

interface ConvoLinkProps {
  isActiveConvo: boolean;
  isPopoverActive: boolean;
  title: string | null;
  ledgerStatus?: string | null;
  onRename: () => void;
  isSmallScreen: boolean;
  localize: (key: any, options?: any) => string;
  children: React.ReactNode;
}

const STATUS_CLASS: Record<string, string> = {
  进行中: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200',
  '仍在处理…': 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200',
  停止中: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100',
  失败: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
  已停止: 'bg-surface-tertiary text-text-secondary',
  已完成: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
};

const ConvoLink: React.FC<ConvoLinkProps> = ({
  isActiveConvo,
  isPopoverActive,
  title,
  ledgerStatus,
  onRename,
  isSmallScreen,
  localize,
  children,
}) => {
  return (
    <div
      className={cn(
        'flex min-w-0 grow items-center gap-2 overflow-hidden rounded-lg px-2',
        isActiveConvo || isPopoverActive ? 'bg-surface-active-alt' : '',
      )}
      title={
        ledgerStatus
          ? `${title ?? localize('com_ui_untitled')} · ${ledgerStatus}`
          : (title ?? undefined)
      }
      aria-current={isActiveConvo ? 'page' : undefined}
      style={{ width: '100%' }}
    >
      {children}
      <div
        className="relative flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden"
        onDoubleClick={(e) => {
          if (isSmallScreen) {
            return;
          }
          e.preventDefault();
          e.stopPropagation();
          onRename();
        }}
        aria-label={
          ledgerStatus
            ? `${title || localize('com_ui_untitled')}，${ledgerStatus}`
            : title || localize('com_ui_untitled')
        }
      >
        <span
          className="relative min-w-0 flex-1 grow overflow-hidden whitespace-nowrap"
          style={{ textOverflow: 'clip' }}
        >
          {title || localize('com_ui_untitled')}
          <span
            className={cn(
              'pointer-events-none absolute bottom-0 right-0 top-0 w-12 bg-gradient-to-l',
              isActiveConvo || isPopoverActive
                ? 'from-surface-active-alt'
                : 'from-surface-primary-alt from-0% to-transparent group-hover:from-surface-active-alt group-hover:from-0%',
            )}
            aria-hidden="true"
          />
        </span>
        {ledgerStatus ? (
          <span
            data-testid="convo-ledger-status"
            className={cn(
              'shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none',
              STATUS_CLASS[ledgerStatus] || 'bg-surface-tertiary text-text-secondary',
            )}
          >
            {ledgerStatus}
          </span>
        ) : null}
      </div>
    </div>
  );
};

export default ConvoLink;
