/**
 * Pico left rail: 新对话 + 搜索 + 技能与连接器 + 文件/材料 + 项目夹/未分组会话.
 * Conversation menus come from LibreChat ConvoOptions (pin/archive/delete/folder).
 */
import { memo, useCallback, lazy, Suspense, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useRecoilValue } from 'recoil';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import { QueryKeys } from 'librechat-data-provider';
import { useQueryClient } from '@tanstack/react-query';
import { Skeleton, Button, TooltipAnchor } from '@librechat/client';
import type { NavLink } from '~/common';
import { useLocalize, useNewConvo } from '~/hooks';
import { clearMessagesCache, cn } from '~/utils';
import store from '~/store';
import ConversationsSection from '~/components/UnifiedSidebar/ConversationsSection';
import { rememberTaskRoute } from '~/components/Workbench/workbenchSession';

const AccountSettings = lazy(() => import('~/components/Nav/AccountSettings'));

type NavItem = {
  id: string;
  label: string;
  icon: PicoIconName;
  path: string;
};

const NAV: NavItem[] = [
  { id: 'search', label: '搜索会话', icon: 'search', path: '/search' },
  { id: 'capability', label: '技能与连接器', icon: 'blocks', path: '/capability' },
  { id: 'files', label: '我的文件', icon: 'folder', path: '/more/files' },
  { id: 'school', label: '学校材料', icon: 'books', path: '/more/files#school' },
];

function isNavItemActive(pathname: string, hash: string, item: NavItem) {
  if (item.id === 'files') {
    return pathname.startsWith('/more/files') && hash !== '#school';
  }
  if (item.id === 'school') {
    return pathname.startsWith('/more/files') && hash === '#school';
  }
  if (item.id === 'capability') {
    return pathname.startsWith('/capability') || pathname.startsWith('/skills');
  }
  return pathname.startsWith(item.path);
}

function Sidebar({
  links: _links,
  expanded,
  onCollapse,
  onExpand,
  onResizeStart: _onResizeStart,
  onResizeKeyboard: _onResizeKeyboard,
}: {
  links: NavLink[];
  expanded: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onResizeStart: (e: React.MouseEvent) => void;
  onResizeKeyboard: (direction: 'shrink' | 'grow') => void;
}) {
  const localize = useLocalize();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const { newConversation } = useNewConvo();
  const conversationId = useRecoilValue(store.conversationIdByIndex(0));

  useEffect(() => {
    rememberTaskRoute(location.pathname, location.search);
  }, [location.pathname, location.search]);

  const onNewTask = useCallback(() => {
    clearMessagesCache(queryClient, conversationId);
    queryClient.invalidateQueries([QueryKeys.messages]);
    newConversation();
    navigate('/c/new');
  }, [queryClient, conversationId, newConversation, navigate]);

  const navButtons = (compact: boolean) =>
    NAV.map((item) => {
      const active = isNavItemActive(location.pathname, location.hash, item);
      const button = (
        <button
          type="button"
          data-testid={`nav-${item.id}`}
          onClick={() => navigate(item.path)}
          className={
            compact
              ? cn(
                  'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
                  active
                    ? 'bg-[color:var(--pico-line-2)] text-[color:var(--pico-ink)] dark:bg-surface-tertiary dark:text-text-primary'
                    : 'text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-line)] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                )
              : cn(
                  'pico-type-sidebar group flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left transition-colors',
                  active
                    ? 'bg-[color:var(--pico-line)] font-medium text-[color:var(--pico-ink)] dark:bg-surface-tertiary dark:text-text-primary'
                    : 'font-normal text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                )
          }
          aria-label={item.label}
          aria-current={active ? 'page' : undefined}
        >
          <span
            className={cn(
              'flex shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]',
              compact ? '' : 'h-6 w-6',
            )}
          >
            <PicoIcon name={item.icon} size="sm" />
          </span>
          {compact ? null : <span className="min-w-0 flex-1 truncate">{item.label}</span>}
        </button>
      );
      if (!compact) {
        return <div key={item.id}>{button}</div>;
      }
      return (
        <TooltipAnchor
          key={item.id}
          description={item.label}
          render={button}
        />
      );
    });

  if (!expanded) {
    return (
      <div className="pico-wb-sidebar flex h-full w-full flex-col items-center bg-[color:var(--pico-sidebar)] py-3 dark:bg-surface-primary-alt">
        <TooltipAnchor
          description="展开侧栏"
          render={
            <Button
              size="icon"
              variant="ghost"
              className="h-9 w-9 rounded-lg"
              onClick={onExpand}
              aria-label="展开侧栏"
            >
              <PicoIcon name="panel" />
            </Button>
          }
        />
        <button
          type="button"
          onClick={onNewTask}
          className="mt-2 flex h-9 w-9 items-center justify-center rounded-lg bg-[color:var(--pico-ink)] text-white transition-colors hover:bg-[color:var(--pico-ink-2)]"
          aria-label="新对话"
          data-testid="nav-new"
        >
          <PicoIcon name="plus" size="sm" />
        </button>
        <nav className="mt-2 flex flex-col items-center gap-1" aria-label="主导航">
          {navButtons(true)}
        </nav>
      </div>
    );
  }

  return (
    <div className="pico-wb-sidebar flex h-full w-full min-w-0 flex-col bg-[color:var(--pico-sidebar)] text-[color:var(--pico-ink)] dark:bg-surface-primary-alt dark:text-text-primary">
      <div className="flex items-start justify-between px-4 pb-1 pt-4">
        <div className="min-w-0">
          <div className="pico-type-body pico-type-medium leading-tight tracking-tight">Pico</div>
        </div>
        <button
          type="button"
          className="rounded-md p-1.5 text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)]"
          onClick={onCollapse}
          aria-label={localize('com_nav_close_sidebar')}
        >
          <PicoIcon name="panel" size="sm" />
        </button>
      </div>

      <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="px-2.5 pb-1">
          <button
            type="button"
            data-testid="new-chat-button"
            onClick={onNewTask}
            className="pico-type-sidebar pico-type-medium flex h-9 w-full items-center justify-center gap-2 rounded-full bg-[color:var(--pico-ink)] text-white shadow-sm transition hover:bg-[color:var(--pico-ink-2)]"
          >
            <PicoIcon name="plus" size="sm" />
            新对话
          </button>
        </div>
        <nav className="mt-1 flex shrink-0 flex-col gap-0.5 px-2.5" aria-label="主导航">
          {navButtons(false)}
        </nav>

        <div
          className="mt-3 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-t border-[color:var(--pico-line)] pt-2"
          data-testid="sidebar-task-history"
        >
          <ConversationsSection />
        </div>
      </div>

      <div className="mt-auto flex min-w-0 shrink-0 items-center gap-1 border-t border-[color:var(--pico-line)] px-3 py-2.5">
        <div className="min-w-0 flex-1 overflow-hidden">
          <Suspense fallback={<Skeleton className="h-8 w-8 rounded-full" />}>
            <AccountSettings />
          </Suspense>
        </div>
      </div>
    </div>
  );
}

export default memo(Sidebar);
