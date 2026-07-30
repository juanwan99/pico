/**
 * Pico workbench left rail — single column WorkBuddy-class IA.
 */
import { memo, useCallback, lazy, Suspense } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useRecoilValue } from 'recoil';
import {
  Plus,
  Bot,
  FolderKanban,
  Blocks,
  Zap,
  MoreHorizontal,
  History,
  Search,
  Gift,
  ChevronDown,
  CircleHelp,
  Bell,
  PanelLeft,
} from 'lucide-react';
import { QueryKeys } from 'librechat-data-provider';
import { useQueryClient } from '@tanstack/react-query';
import { Skeleton, Button, TooltipAnchor } from '@librechat/client';
import type { NavLink } from '~/common';
import { useLocalize, useNewConvo } from '~/hooks';
import { clearMessagesCache, cn } from '~/utils';
import store from '~/store';
import TaskListSection from '~/components/Workbench/TaskListSection';

const AccountSettings = lazy(() => import('~/components/Nav/AccountSettings'));

type NavItem = {
  id: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  path?: string;
  action?: 'new-task' | 'more';
  badge?: string;
};

const NAV: NavItem[] = [
  { id: 'new', label: '新建任务', icon: Plus, action: 'new-task' },
  { id: 'agents', label: '助理', icon: Bot, path: '/assistants' },
  { id: 'projects', label: '项目', icon: FolderKanban, path: '/projects' },
  { id: 'skills', label: '专家·技能·连接器', icon: Blocks, path: '/capability' },
  { id: 'auto', label: '自动化', icon: Zap, path: '/automation' },
  { id: 'more', label: '更多', icon: MoreHorizontal, path: '/more', badge: '资料库·灵感' },
];

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

  const onNewTask = useCallback(() => {
    clearMessagesCache(queryClient, conversationId);
    queryClient.invalidateQueries([QueryKeys.messages]);
    newConversation();
    navigate('/c/new');
  }, [queryClient, conversationId, newConversation, navigate]);

  if (!expanded) {
    return (
      <div className="pico-wb-sidebar flex h-full w-full flex-col items-center gap-2 bg-[#f0f0f0] py-3 dark:bg-surface-primary-alt">
        <Button size="icon" variant="ghost" className="h-9 w-9" onClick={onExpand} aria-label="展开">
          <PanelLeft className="h-5 w-5" />
        </Button>
        <button
          type="button"
          onClick={onNewTask}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-[#1a1a1a] text-white"
          aria-label="新建任务"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="pico-wb-sidebar flex h-full w-full min-w-0 flex-col bg-[#f0f0f0] text-[#1a1a1a] dark:bg-surface-primary-alt dark:text-text-primary">
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
                <History className="h-4 w-4" />
              </button>
            }
          />
          <button
            type="button"
            className="rounded-md p-1.5 hover:bg-black/[0.04]"
            onClick={() => navigate('/search')}
            aria-label="搜索"
          >
            <Search className="h-4 w-4" />
          </button>
          <button type="button" className="rounded-md p-1.5 hover:bg-black/[0.04]" aria-label="活动">
            <Gift className="h-4 w-4" />
          </button>
          <button
            type="button"
            className="rounded-md p-1.5 hover:bg-black/[0.04]"
            onClick={onCollapse}
            aria-label={localize('com_nav_close_sidebar')}
          >
            <PanelLeft className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="mt-3 flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="px-2.5 pb-1">
          <button
            type="button"
            data-testid="new-chat-button"
            onClick={onNewTask}
            className="flex h-9 w-full items-center justify-center gap-2 rounded-full bg-[#1a1a1a] text-[13px] font-medium text-white shadow-sm transition hover:bg-black"
          >
            <Plus className="h-4 w-4" strokeWidth={2.25} />
            新建任务
          </button>
        </div>
        <nav className="mt-1 flex shrink-0 flex-col gap-0.5 px-2.5" aria-label="主导航">
          {NAV.filter((item) => item.action !== 'new-task').map((item) => {
            const Icon = item.icon;
            let active = false;
            if (location.pathname.startsWith('/agents') || location.pathname.startsWith('/assistants')) {
              active = item.id === 'agents';
            } else if (location.pathname.startsWith('/projects')) {
              active = item.id === 'projects';
            } else if (
              location.pathname.startsWith('/skills') ||
              location.pathname.startsWith('/capability')
            ) {
              active = item.id === 'skills';
            } else if (location.pathname.startsWith('/automation')) {
              active = item.id === 'auto';
            } else if (location.pathname.startsWith('/more')) {
              active = item.id === 'more';
            } else if (item.path) {
              active = location.pathname.startsWith(item.path);
            }

            return (
              <button
                key={item.id}
                type="button"
                data-testid={`nav-${item.id}`}
                onClick={() => {
                  if (item.path) {
                    navigate(item.path);
                  }
                }}
                className={cn(
                  'group flex h-9 w-full items-center gap-2.5 rounded-[10px] px-2.5 text-left text-[13.5px] transition-colors',
                  active
                    ? 'bg-[#e4e4e4] font-medium text-[#1a1a1a] dark:bg-surface-tertiary dark:text-text-primary'
                    : 'font-normal text-[#3d3d3d] hover:bg-[#e8e8e8] dark:text-text-secondary dark:hover:bg-surface-tertiary',
                )}
              >
                <span className="flex h-6 w-6 shrink-0 items-center justify-center text-[#4a4a4a]">
                  <Icon className="h-[18px] w-[18px]" strokeWidth={1.75} />
                </span>
                <span className="min-w-0 flex-1 truncate">{item.label}</span>
                {item.badge ? (
                  <span className="shrink-0 text-[11px] text-[#9a9a9a]">{item.badge}</span>
                ) : null}
              </button>
            );
          })}
        </nav>

        <TaskListSection />

        <div className="mt-1 shrink-0 px-3.5 pb-2">
          <button
            type="button"
            className="flex h-8 w-full items-center gap-1 rounded-md px-1.5 text-[12.5px] text-[#6b6b6b] hover:bg-[#e8e8e8]"
          >
            <span>空间 (1)</span>
            <ChevronDown className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="mt-0.5 flex h-8 w-full items-center gap-2 rounded-md px-1.5 text-[12.5px] text-[#3d3d3d] hover:bg-[#e8e8e8]"
          >
            <FolderKanban className="h-3.5 w-3.5 text-[#6b6b6b]" />
            <span className="truncate">默认工作空间</span>
            <span className="ml-auto text-[#b0b0b0]">›</span>
          </button>
        </div>
      </div>

      <div className="mt-auto flex items-center gap-1 border-t border-black/[0.04] px-3 py-2.5">
        <div className="min-w-0 flex-1">
          <Suspense fallback={<Skeleton className="h-8 w-8 rounded-full" />}>
            <AccountSettings />
          </Suspense>
        </div>
        <button type="button" className="rounded-md p-1.5 text-[#6b6b6b] hover:bg-black/[0.04]" aria-label="通知">
          <Bell className="h-4 w-4" />
        </button>
        <button type="button" className="rounded-md p-1.5 text-[#6b6b6b] hover:bg-black/[0.04]" aria-label="帮助">
          <CircleHelp className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export default memo(Sidebar);
