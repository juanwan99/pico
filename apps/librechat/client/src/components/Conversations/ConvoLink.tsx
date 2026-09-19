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
  进行中: 'bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]',
  '仍在处理…': 'bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]',
  停止中: 'bg-[color:var(--pico-amber-wash)] text-[color:var(--pico-amber)]',
  失败: 'bg-[color:var(--pico-red-wash)] text-[color:var(--pico-red)]',
  已停止: 'bg-[color:var(--pico-surface-2)] text-[color:var(--pico-ink-2)]',
  已完成: 'bg-[color:var(--pico-mint-wash)] text-[color:var(--pico-mint-dark)]',
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
        'flex min-w-0 grow items-start gap-2 overflow-hidden rounded-lg px-2 py-1',
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
        className="relative flex min-w-0 flex-1 flex-col items-stretch gap-0.5 overflow-hidden pt-0.5"
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
          className="min-w-0 w-full break-words leading-snug line-clamp-2"
          data-testid="convo-title"
        >
          {title || localize('com_ui_untitled')}
        </span>
        {ledgerStatus ? (
          <span
            data-testid="convo-ledger-status"
            className={cn(
              'pico-type-aux self-start shrink-0 rounded-full px-1.5 py-0.5 font-medium leading-none',
              STATUS_CLASS[ledgerStatus] ||
                'bg-[color:var(--pico-surface-2)] text-[color:var(--pico-ink-2)]',
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
