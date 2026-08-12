/**
 * Pico workbench left rail — single column WorkBuddy-class IA.
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
import TeacherTaskHome from '~/components/Conversations/TeacherTaskHome';
import { usePicoConversationStatusMap } from '~/hooks/Pico/usePicoConversationStatusMap';
import { rememberTaskRoute } from '~/components/Workbench/workbenchSession';

const AccountSettings = lazy(() => import('~/components/Nav/AccountSettings'));

type NavItem = {
  id: string;
  label: string;
  icon: PicoIconName;
  path?: string;
  action?: 'new-task' | 'more';
  badge?: string;
};

const NAV: NavItem[] = [
  { id: 'new', label: '新建任务', icon: 'plus', action: 'new-task' },
  { id: 'agents', label: '助理', icon: 'bot', path: '/assistants' },
  { id: 'projects', label: '项目', icon: 'folder', path: '/projects' },
  {
    id: 'skills',
    label: '专家·技能·连接器',
    icon: 'blocks',
    path: '/capability',
  },
  { id: 'auto', label: '自动化', icon: 'zap', path: '/automation' },
  {
    id: 'more',
    label: '更多',
    icon: 'more',
    path: '/more',
    action: 'more',
    badge: '资料库·灵感',
  },
];

const MORE_ITEMS = [
  { label: '我的文件', icon: 'folder-open' as PicoIconName, path: '/more/files' },
  { label: '我的邮箱', icon: 'mail' as PicoIconName, path: '/capability/connectors/c3' },
  {
    label: '腾讯文档',
    icon: 'doc' as PicoIconName,
    path: '/capability/connectors/c5',
    divider: true,
  },
  {
    label: 'ima知识库',
    icon: 'books' as PicoIconName,
    path: '/capability/connectors/c4?provider=ima',
  },
  {
    label: '乐享知识库',
    icon: 'books' as PicoIconName,
    path: '/capability/connectors/c4?provider=lexiang',
  },
  {
    label: '灵感',
    icon: 'lightbulb' as PicoIconName,
    path: '/capability?tab=skills',
    divider: true,
  },
] as const;

function isNavItemActive(pathname: string, item: NavItem) {
  if (pathname.startsWith('/agents') || pathname.startsWith('/assistants')) {
    return item.id === 'agents';
  }
  if (pathname.startsWith('/projects')) {
    return item.id === 'projects';
  }
  if (pathname.startsWith('/skills') || pathname.startsWith('/capability')) {
    return item.id === 'skills';
  }
  if (pathname.startsWith('/automation')) {
    return item.id === 'auto';
  }
  if (pathname.startsWith('/more')) {
    return item.id === 'more';
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

  const {
    tasks: picoTasks,
    loading: isTaskHistoryLoading,
    error: taskHistoryError,
    refresh: refreshTaskHistory,
  } = usePicoConversationStatusMap(true);
  const handleTaskOpen = useCallback(() => {
    // Desktop rail stays open; TeacherTaskHome still needs the onOpen callback.
  }, []);

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
          className="mt-2 flex h-9 w-9 items-center justify-center rounded-lg bg-[color:var(--pico-ink)] text-white transition-colors hover:bg-black"
          aria-label="新建任务"
        >
          <PicoIcon name="plus" size="sm" />
        </button>
        <nav className="mt-2 flex flex-col items-center gap-1" aria-label="主导航">
          {NAV.filter((item) => item.action !== 'new-task').map((item) => {
            const active = isNavItemActive(location.pathname, item);

            return (
              <TooltipAnchor
                key={item.id}
                description={item.label}
                render={
                  <button
                    type="button"
                    data-testid={`nav-${item.id}`}
                    onClick={() => item.path && navigate(item.path)}
                    className={cn(
                      'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
                      active
                        ? 'bg-[#dedede] text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary'
                        : 'text-[#555] hover:bg-[#e4e4e4] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                    )}
                    aria-label={item.label}
                    aria-current={active ? 'page' : undefined}
                  >
                    <PicoIcon name={item.icon} size="sm" />
                  </button>
                }
              />
            );
          })}
        </nav>
        <div className="my-2 h-px w-6 bg-black/[0.06] dark:bg-white/10" />
        <TooltipAnchor
          description="空间"
          render={
            <button
              type="button"
              onClick={() => navigate('/workspaces')}
              className={cn(
                'flex h-9 w-9 items-center justify-center rounded-lg transition-colors',
                location.pathname.startsWith('/workspaces')
                  ? 'bg-[#dedede] text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary'
                  : 'text-[#555] hover:bg-[#e4e4e4] dark:text-text-secondary dark:hover:bg-surface-tertiary',
              )}
              aria-label="空间"
              aria-current={location.pathname.startsWith('/workspaces') ? 'page' : undefined}
            >
              <PicoIcon name="folder-open" size="sm" />
            </button>
          }
        />
      </div>
    );
  }

  return (
    <div className="pico-wb-sidebar flex h-full w-full min-w-0 flex-col bg-[color:var(--pico-sidebar)] text-[color:var(--pico-ink)] dark:bg-surface-primary-alt dark:text-text-primary">
      <div className="flex items-start justify-between px-4 pb-1 pt-4">
        <div className="min-w-0">
          <div className="text-[15px] font-semibold leading-tight tracking-tight">Pico</div>
          <div className="mt-0.5 text-[11px] leading-none text-[#8c8c8c]">v0.8.7</div>
        </div>
        <div className="flex items-center gap-0.5 text-[#6b6b6b]">
          <TooltipAnchor
            description="任务历史"
            render={
              <button
                type="button"
                className="rounded-md p-1.5 hover:bg-black/[0.04]"
                onClick={() => navigate('/search')}
                aria-label="任务历史"
              >
                <PicoIcon name="clock" size="sm" />
              </button>
            }
          />
          <button
            type="button"
            className="rounded-md p-1.5 hover:bg-black/[0.04]"
            onClick={() => navigate('/search')}
            aria-label="搜索"
          >
            <PicoIcon name="search" size="sm" />
          </button>
          <TooltipAnchor
            description="活动与更多"
            render={
              <button
                type="button"
                className="rounded-md p-1.5 hover:bg-black/[0.04]"
                onClick={() => navigate('/more')}
                aria-label="活动与更多"
              >
                <PicoIcon name="gift" size="sm" />
              </button>
            }
          />
          <button
            type="button"
            className="rounded-md p-1.5 hover:bg-black/[0.04]"
            onClick={onCollapse}
            aria-label={localize('com_nav_close_sidebar')}
          >
            <PicoIcon name="panel" size="sm" />
          </button>
        </div>
      </div>

      <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="px-2.5 pb-1">
          <button
            type="button"
            data-testid="new-chat-button"
            onClick={onNewTask}
            className="flex h-9 w-full items-center justify-center gap-2 rounded-full bg-[color:var(--pico-ink)] text-[13px] font-medium text-white shadow-sm transition hover:bg-black"
          >
            <PicoIcon name="plus" size="sm" />
            新建任务
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
                    'group flex h-9 w-full items-center gap-2.5 rounded-lg px-2.5 text-left text-[13.5px] transition-colors',
                    active
                      ? 'bg-[#e4e4e4] font-medium text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary'
                      : 'font-normal text-[#3d3d3d] hover:bg-[#e8e8e8] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                  )}
                  aria-current={active ? 'page' : undefined}
                  aria-expanded={item.action === 'more' ? Boolean(moreMenu) : undefined}
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center text-[#4a4a4a]">
                    <PicoIcon name={item.icon} size="sm" />
                  </span>
                  <span className="min-w-0 flex-1 truncate">{item.label}</span>
                  {item.badge ? (
                    <span className="shrink-0 text-[11px] text-[#9a9a9a]">{item.badge}</span>
                  ) : null}
                </button>
                {item.action === 'more' && moreMenu ? (
                  <div
                    className="fixed z-[160] w-40 rounded-lg border border-black/[0.08] bg-white p-1.5 shadow-[0_10px_30px_rgba(0,0,0,0.12)]"
                    style={{ left: moreMenu.left, top: moreMenu.top }}
                    role="menu"
                    aria-label="更多 · 资料库·灵感"
                  >
                    {MORE_ITEMS.map((menuItem) => {
                      return (
                        <div key={menuItem.label}>
                          {'divider' in menuItem && menuItem.divider ? (
                            <div className="my-1 h-px bg-black/[0.06]" />
                          ) : null}
                          <button
                            type="button"
                            role="menuitem"
                            className="flex h-8 w-full items-center gap-2 rounded-md px-2 text-left text-[13px] text-[#3d3d3d] hover:bg-[#f2f2f2]"
                            onClick={() => {
                              setMoreMenu(null);
                              navigate(menuItem.path);
                            }}
                          >
                            <PicoIcon name={menuItem.icon} size="sm" className="text-[#5d5d5d]" />
                            <span>{menuItem.label}</span>
                          </button>
                        </div>
                      );
                    })}
                  </div>
                ) : null}
              </div>
            );
          })}
        </nav>

        <div
          className="mt-3 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden border-t border-[color:var(--pico-line)] pt-2"
          data-testid="sidebar-task-history"
        >
          <div className="mb-1 flex items-center justify-between px-2.5">
            <span className="text-[12px] font-medium text-[color:var(--pico-ink-2)]">任务历史</span>
          </div>
          <TeacherTaskHome
            tasks={picoTasks}
            loading={isTaskHistoryLoading}
            error={taskHistoryError}
            onRetry={refreshTaskHistory}
            onOpen={handleTaskOpen}
          />
        </div>

        <div className="shrink-0 border-t border-[color:var(--pico-line)] px-3.5 py-2">
          <button
            type="button"
            onClick={() => navigate('/workspaces')}
            className="flex h-8 w-full min-w-0 items-center gap-1 rounded-lg px-1.5 text-[12.5px] text-[color:var(--pico-ink-2)] hover:bg-[color:var(--pico-surface-2)]"
          >
            <span>空间</span>
            <PicoIcon name="chevron" size="sm" />
          </button>
          <button
            type="button"
            onClick={() => navigate('/workspaces')}
            className="mt-0.5 flex h-8 w-full min-w-0 items-center gap-2 rounded-lg px-1.5 text-[12.5px] text-[color:var(--pico-ink)] hover:bg-[color:var(--pico-surface-2)]"
          >
            <PicoIcon name="folder" size="sm" className="text-[color:var(--pico-ink-2)]" />
            <span className="min-w-0 flex-1 truncate">管理工作空间</span>
            <span className="shrink-0 text-[color:var(--pico-ink-3)]">›</span>
          </button>
        </div>
      </div>

      <div className="mt-auto flex min-w-0 shrink-0 items-center gap-1 border-t border-[color:var(--pico-line)] px-3 py-2.5">
        <div className="min-w-0 flex-1 overflow-hidden">
          <Suspense fallback={<Skeleton className="h-8 w-8 rounded-full" />}>
            <AccountSettings />
          </Suspense>
        </div>
        <button
          type="button"
          className="rounded-md p-1.5 text-[#6b6b6b] hover:bg-black/[0.04]"
          aria-label="通知"
        >
          <PicoIcon name="bell" size="sm" />
        </button>
        <button
          type="button"
          className="rounded-md p-1.5 text-[#6b6b6b] hover:bg-black/[0.04]"
          aria-label="帮助"
        >
          <PicoIcon name="help" size="sm" />
        </button>
      </div>
    </div>
  );
}

export default memo(Sidebar);
