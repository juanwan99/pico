/**
 * Pico workbench left rail — pixel-aligned to WorkBuddy home IA (clean-room).
 * Single column only. No dual rail.
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
  { id: 'agents', label: '助理', icon: Bot, path: '/agents' },
  { id: 'projects', label: '项目', icon: FolderKanban, path: '/projects' },
  { id: 'skills', label: '专家·技能·连接器', icon: Blocks, path: '/skills' },
  { id: 'auto', label: '自动化', icon: Zap, path: '/c/new' },
  { id: 'more', label: '更多', icon: MoreHorizontal, action: 'more', badge: '资料库·灵感' },
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

  const isNewTask =
    location.pathname === '/c/new' ||
    location.pathname === '/' ||
    /^\/c\/[^/]+$/.test(location.pathname);

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
      {/* Brand row */}
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
        </div>
      </div>

      {/* Primary nav — vertical list, one column */}
      <nav className="mt-3 flex flex-1 flex-col gap-0.5 px-2.5" aria-label="主导航">
        {NAV.map((item) => {
          const Icon = item.icon;
          let active = false;
          if (item.action === 'new-task') {
            active = isNewTask && !location.pathname.startsWith('/agents') && !location.pathname.startsWith('/projects') && !location.pathname.startsWith('/skills');
            // On any chat route treat as new-task home when path is /c/*
            active = location.pathname.startsWith('/c') || location.pathname === '/';
          } else if (item.path) {
            active = location.pathname.startsWith(item.path);
            if (item.id === 'auto') {
              active = false;
            }
          }
          // If on agents, only agents active
          if (location.pathname.startsWith('/agents')) {
            active = item.id === 'agents';
          } else if (location.pathname.startsWith('/projects')) {
            active = item.id === 'projects';
          } else if (location.pathname.startsWith('/skills')) {
            active = item.id === 'skills';
          } else if (location.pathname.startsWith('/c') || location.pathname === '/') {
            active = item.id === 'new';
          }

          return (
            <button
              key={item.id}
              type="button"
              data-testid={item.action === 'new-task' ? 'new-chat-button' : `nav-${item.id}`}
              onClick={() => {
                if (item.action === 'new-task') {
                  onNewTask();
                  return;
                }
                if (item.action === 'more') {
                  navigate('/prompts');
                  return;
                }
                if (item.path) {
                  navigate(item.path);
                }
              }}
              className={cn(
                'group flex h-10 w-full items-center gap-2.5 rounded-[10px] px-2.5 text-left text-[13.5px] transition-colors',
                active
                  ? 'bg-[#e6e6e6] font-medium text-[#1a1a1a]'
                  : 'font-normal text-[#3d3d3d] hover:bg-[#e8e8e8]',
              )}
            >
              <span
                className={cn(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded-full',
                  item.id === 'new' && active
                    ? 'bg-transparent text-[#1a1a1a]'
                    : 'text-[#4a4a4a]',
                )}
              >
                <Icon className="h-[17px] w-[17px]" strokeWidth={1.75} />
              </span>
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
              {item.badge ? (
                <span className="shrink-0 text-[11px] text-[#9a9a9a]">{item.badge}</span>
              ) : null}
            </button>
          );
        })}

        {/* 空间 */}
        <div className="mt-4 px-1">
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
            <span className="truncate">项目新手指引</span>
            <span className="ml-auto text-[#b0b0b0]">›</span>
          </button>
        </div>
      </nav>

      {/* User footer */}
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
