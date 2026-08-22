/**
 * Pico left rail — Grok-like: 新对话 + 历史 + 一个「更多」.
 * Conversation menus come from LibreChat ConvoOptions (pin/archive/delete/folder).
 */
import { memo, useCallback, lazy, Suspense, useEffect, useRef, useState } from 'react';
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
  path?: string;
  action?: 'new-task' | 'more';
};

const NAV: NavItem[] = [
  { id: 'new', label: '新对话', icon: 'plus', action: 'new-task' },
  { id: 'more', label: '更多', icon: 'more', action: 'more' },
];

const MORE_ITEMS = [
  { label: '搜索会话', icon: 'search' as PicoIconName, path: '/search' },
  { label: '助理', icon: 'bot' as PicoIconName, path: '/assistants' },
  { label: '项目', icon: 'folder' as PicoIconName, path: '/projects' },
  { label: '专家·技能·连接器', icon: 'blocks' as PicoIconName, path: '/capability' },
  { label: '自动化', icon: 'zap' as PicoIconName, path: '/automation' },
  { label: '空间', icon: 'folder-open' as PicoIconName, path: '/workspaces', divider: true },
  { label: '我的文件', icon: 'folder-open' as PicoIconName, path: '/more/files' },
  { label: '学校材料', icon: 'folder-open' as PicoIconName, path: '/more/files#school' },
  { label: '灵感', icon: 'lightbulb' as PicoIconName, path: '/capability?tab=skills' },
] as const;

function isNavItemActive(pathname: string, item: NavItem) {
  if (item.action === 'more') {
    return (
      pathname.startsWith('/agents') ||
      pathname.startsWith('/assistants') ||
      pathname.startsWith('/projects') ||
      pathname.startsWith('/skills') ||
      pathname.startsWith('/capability') ||
      pathname.startsWith('/automation') ||
      pathname.startsWith('/more') ||
      pathname.startsWith('/workspaces') ||
      pathname.startsWith('/search')
    );
  }
  return Boolean(item.path && pathname.startsWith(item.path));
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
  const [moreMenu, setMoreMenu] = useState<{
    left: number;
    top: number;
  } | null>(null);
  const moreRegionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    rememberTaskRoute(location.pathname, location.search);
  }, [location.pathname, location.search]);

  const onNewTask = useCallback(() => {
    clearMessagesCache(queryClient, conversationId);
    queryClient.invalidateQueries([QueryKeys.messages]);
    newConversation();
    navigate('/c/new');
  }, [queryClient, conversationId, newConversation, navigate]);

  useEffect(() => {
    if (!moreMenu) {
      return;
    }
    const closeOnOutsidePress = (event: PointerEvent) => {
      if (!moreRegionRef.current?.contains(event.target as Node)) {
        setMoreMenu(null);
      }
    };
    document.addEventListener('pointerdown', closeOnOutsidePress);
    return () => document.removeEventListener('pointerdown', closeOnOutsidePress);
  }, [moreMenu]);

  const moreMenuPanel = moreMenu ? (
    <div
      className="fixed z-[160] w-44 rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-1.5 shadow-[var(--pico-shadow-raised)]"
      style={{ left: moreMenu.left, top: moreMenu.top }}
      role="menu"
      aria-label="更多"
      data-testid="nav-more-menu"
    >
      {MORE_ITEMS.map((menuItem) => {
        return (
          <div key={menuItem.label}>
            {'divider' in menuItem && menuItem.divider ? (
              <div className="my-1 h-px bg-[color:var(--pico-line)]" />
            ) : null}
            <button
              type="button"
              role="menuitem"
              className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)]"
              onClick={() => {
                setMoreMenu(null);
                navigate(menuItem.path);
              }}
            >
              <PicoIcon name={menuItem.icon} size="sm" className="text-[color:var(--pico-ink-2)]" />
              <span>{menuItem.label}</span>
            </button>
          </div>
        );
      })}
    </div>
  ) : null;

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
          {NAV.filter((item) => item.action !== 'new-task').map((item) => {
            const active = isNavItemActive(location.pathname, item);
            return (
              <div key={item.id} ref={item.action === 'more' ? moreRegionRef : undefined}>
                <TooltipAnchor
                  description={item.label}
                  render={
                    <button
                      type="button"
                      data-testid={`nav-${item.id}`}
                      onClick={(event) => {
                        if (item.action === 'more') {
                          const rect = event.currentTarget.getBoundingClientRect();
                          setMoreMenu((current) =>
                            current ? null : { left: rect.right + 8, top: rect.top - 2 },
                          );
                          return;
                        }
                        if (item.path) {
                          navigate(item.path);
                        }
                      }}
                      className={cn(
                        'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
                        active
                          ? 'bg-[color:var(--pico-line-2)] text-[color:var(--pico-ink)] dark:bg-surface-tertiary dark:text-text-primary'
                          : 'text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-line)] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                      )}
                      aria-label={item.label}
                      aria-expanded={item.action === 'more' ? Boolean(moreMenu) : undefined}
                    >
                      <PicoIcon name={item.icon} size="sm" />
                    </button>
                  }
                />
                {item.action === 'more' ? moreMenuPanel : null}
              </div>
            );
          })}
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
          {NAV.filter((item) => item.action !== 'new-task').map((item) => {
            const active = isNavItemActive(location.pathname, item);
            return (
              <div
                key={item.id}
                ref={item.action === 'more' ? moreRegionRef : undefined}
                className="relative"
              >
                <button
                  type="button"
                  data-testid={`nav-${item.id}`}
                  onClick={(event) => {
                    if (item.action === 'more') {
                      const rect = event.currentTarget.getBoundingClientRect();
                      setMoreMenu((current) =>
                        current ? null : { left: rect.right - 10, top: rect.top - 2 },
                      );
                      return;
                    }
                    if (item.path) {
                      navigate(item.path);
                    }
                  }}
                  className={cn(
                    'pico-type-sidebar group flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left transition-colors',
                    active
                      ? 'bg-[color:var(--pico-line)] font-medium text-[color:var(--pico-ink)] dark:bg-surface-tertiary dark:text-text-primary'
                      : 'font-normal text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                  )}
                  aria-expanded={item.action === 'more' ? Boolean(moreMenu) : undefined}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]">
                    <PicoIcon name={item.icon} size="sm" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                </button>
                {item.action === 'more' ? moreMenuPanel : null}
              </div>
            );
          })}
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
