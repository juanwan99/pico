/**
 * Project workspace — 动态 / 计划 / 任务 / 资产 + 右侧配置轨
 * Clean-room IA from WorkBuddy research; reuses LibreChat project chats.
 */
import { useCallback, useMemo, useState } from 'react';
import { useRecoilValue } from 'recoil';
import { useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  Folder,
  Plus,
  Search,
  Upload,
  FolderPlus,
  MessageSquare,
} from 'lucide-react';
import { useNavigate, useParams } from 'react-router-dom';
import { QueryKeys } from 'librechat-data-provider';
import type { ConversationListResponse } from 'librechat-data-provider';
import { Spinner } from '@librechat/client';
import { useConversationsInfiniteQuery, useProjectQuery } from '~/data-provider';
import { useLocalize, useNewConvo } from '~/hooks';
import { cn, clearMessagesCache } from '~/utils';
import ProjectChatList from './ProjectChatList';
import store from '~/store';

type TabId = 'dynamic' | 'plan' | 'tasks' | 'assets';

const TABS: { id: TabId; label: string }[] = [
  { id: 'dynamic', label: '动态' },
  { id: 'plan', label: '计划' },
  { id: 'tasks', label: '任务' },
  { id: 'assets', label: '资产' },
];

const RAIL = [
  { id: 'instruction', label: '指令', hint: '项目级系统提示与约束' },
  { id: 'connector', label: '连接器', hint: '绑定 MCP / 外部连接' },
  { id: 'expert', label: '专家', hint: '默认可召唤的专家' },
  { id: 'skill', label: '技能', hint: '项目可用技能集' },
  { id: 'automation', label: '自动化', hint: '项目级定时任务' },
] as const;

const PLAN_COLUMNS = [
  { id: 'todo', label: '待开始', count: 0 },
  { id: 'doing', label: '进行中', count: 0 },
  { id: 'paused', label: '已暂停', count: 0 },
] as const;

export default function ProjectWorkspace() {
  const localize = useLocalize();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { projectId = '' } = useParams();
  const [tab, setTab] = useState<TabId>('tasks');
  const { data: project, isLoading: isProjectLoading } = useProjectQuery(projectId);
  const conversation = useRecoilValue(store.conversationByIndex(0));
  const { newConversation } = useNewConvo();
  const activeProjectId = project?._id;

  const {
    data,
    fetchNextPage,
    isFetchingNextPage,
    isLoading: isConversationsLoading,
  } = useConversationsInfiniteQuery(
    {
      projectId: activeProjectId,
      sortBy: 'updatedAt',
      sortDirection: 'desc',
    },
    {
      enabled: Boolean(activeProjectId),
      staleTime: 30000,
      cacheTime: 300000,
    },
  );

  const conversations = useMemo(
    () => data?.pages.flatMap((page) => page.conversations) ?? [],
    [data?.pages],
  );

  const hasNextPage = useMemo(() => {
    const pages = data?.pages;
    if (!pages?.length) {
      return false;
    }
    const lastPage: ConversationListResponse = pages[pages.length - 1];
    return lastPage.nextCursor !== null;
  }, [data?.pages]);

  const startProjectChat = useCallback(() => {
    if (!activeProjectId) {
      return;
    }
    clearMessagesCache(queryClient, conversation?.conversationId);
    queryClient.invalidateQueries([QueryKeys.messages]);
    newConversation({ template: { chatProjectId: activeProjectId } });
  }, [activeProjectId, conversation?.conversationId, newConversation, queryClient]);

  if (isProjectLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Spinner className="text-text-primary" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-text-secondary">
        {localize('com_ui_project_not_found')}
      </div>
    );
  }

  return (
    <main className="flex h-full min-h-0 bg-[#fafafa] text-[#1a1a1a] dark:bg-presentation dark:text-text-primary">
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-black/[0.06] bg-white px-4 pb-0 pt-3 dark:border-border-light dark:bg-surface-primary">
          <button
            type="button"
            onClick={() => navigate('/projects')}
            className="mb-2 inline-flex items-center gap-1 text-[12.5px] text-[#6b6b6b] hover:text-[#1a1a1a]"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            全部项目
          </button>
          <div className="mb-3 flex items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[#edf1f4]">
              <Folder className="h-5 w-5 text-[#3d3d3d]" />
            </span>
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-[18px] font-semibold tracking-tight">{project.name}</h1>
              {project.description ? (
                <p className="mt-0.5 line-clamp-2 text-[12.5px] text-[#6b6b6b]">
                  {project.description}
                </p>
              ) : (
                <p className="mt-0.5 text-[12.5px] text-[#9a9a9a]">多人协同，打造超级团队</p>
              )}
            </div>
            <button
              type="button"
              onClick={startProjectChat}
              className="inline-flex shrink-0 items-center gap-1 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] font-medium text-white"
            >
              <Plus className="h-3.5 w-3.5" />
              新任务
            </button>
          </div>
          <div className="flex gap-1">
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  'rounded-t-lg px-3.5 py-2 text-[13px] font-medium',
                  tab === t.id
                    ? 'border-b-2 border-[#1a1a1a] text-[#1a1a1a] dark:border-white dark:text-text-primary'
                    : 'text-[#8c8c8c]',
                )}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          {tab === 'dynamic' && (
            <div className="mx-auto max-w-2xl space-y-3">
              <div className="flex gap-2">
                <button
                  type="button"
                  className="rounded-full bg-[#1a1a1a] px-3 py-1 text-[12px] text-white"
                >
                  与我相关
                </button>
                <button
                  type="button"
                  className="rounded-full bg-white px-3 py-1 text-[12px] text-[#6b6b6b] ring-1 ring-black/[0.06]"
                >
                  成员动态
                </button>
              </div>
              <div className="rounded-2xl border border-black/[0.06] bg-white p-4 dark:border-border-light dark:bg-surface-secondary">
                <textarea
                  className="w-full resize-none bg-transparent text-[13px] outline-none placeholder:text-[#b0b0b0]"
                  rows={3}
                  placeholder="发布留言"
                />
              </div>
              <div className="rounded-2xl border border-dashed border-black/[0.08] px-4 py-10 text-center text-[13px] text-[#9a9a9a]">
                暂无成员动态。项目内任务完成与配置变更将出现在此。
              </div>
            </div>
          )}

          {tab === 'plan' && (
            <div className="grid h-full min-h-[320px] grid-cols-1 gap-3 md:grid-cols-3">
              {PLAN_COLUMNS.map((col) => (
                <div
                  key={col.id}
                  className="flex min-h-[280px] flex-col rounded-2xl border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-secondary"
                >
                  <div className="flex items-center justify-between border-b border-black/[0.05] px-3 py-2.5">
                    <span className="text-[13px] font-medium">
                      {col.label}{' '}
                      <span className="text-[#9a9a9a]">{col.count}</span>
                    </span>
                    <button type="button" className="text-[#9a9a9a]" aria-label="添加">
                      <Plus className="h-4 w-4" />
                    </button>
                  </div>
                  <div className="flex flex-1 items-center justify-center p-3 text-[12px] text-[#b0b0b0]">
                    拖拽卡片后置 · 可从任务同步
                  </div>
                </div>
              ))}
            </div>
          )}

          {tab === 'tasks' && (
            <div className="mx-auto max-w-3xl">
              <p className="mb-3 text-[12.5px] text-[#8c8c8c]">
                你的任务是私密的，除非你共享它们
              </p>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px]">全部任务</span>
                <span className="rounded-full bg-white px-2.5 py-1 text-[12px] ring-1 ring-black/[0.06]">
                  全部来源
                </span>
                <div className="ml-auto flex items-center gap-1.5 rounded-lg bg-white px-2 py-1 ring-1 ring-black/[0.06]">
                  <Search className="h-3.5 w-3.5 text-[#9a9a9a]" />
                  <input
                    className="w-36 bg-transparent text-[12.5px] outline-none"
                    placeholder="搜索任务标题"
                  />
                </div>
              </div>
              <ProjectChatList
                conversations={conversations}
                isLoading={isConversationsLoading}
                isFetchingNextPage={isFetchingNextPage}
                hasNextPage={hasNextPage}
                sortBy="updatedAt"
                emptyLabel="暂无项目任务"
                loadMore={() => fetchNextPage()}
              />
            </div>
          )}

          {tab === 'assets' && (
            <div className="mx-auto max-w-3xl">
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-lg bg-[#1a1a1a] px-3 py-1.5 text-[12.5px] text-white"
                >
                  <FolderPlus className="h-3.5 w-3.5" />
                  新建文件夹
                </button>
                <button
                  type="button"
                  className="inline-flex items-center gap-1 rounded-lg border border-black/[0.08] bg-white px-3 py-1.5 text-[12.5px]"
                >
                  <Upload className="h-3.5 w-3.5" />
                  上传文件
                </button>
                <span className="ml-auto text-[12px] text-[#8c8c8c]">
                  存储空间已用 — / 托管配额（服务端 P1）
                </span>
              </div>
              <div className="rounded-2xl border border-black/[0.06] bg-white dark:border-border-light dark:bg-surface-secondary">
                <div className="grid grid-cols-[1fr_80px_100px_80px] gap-2 border-b border-black/[0.05] px-4 py-2 text-[11px] text-[#9a9a9a]">
                  <span>名称</span>
                  <span>类型</span>
                  <span>更新时间</span>
                  <span>大小</span>
                </div>
                <div className="flex flex-col items-center justify-center gap-2 px-4 py-16 text-[#9a9a9a]">
                  <Folder className="h-8 w-8 opacity-40" />
                  <p className="text-[13px]">空目录</p>
                  <p className="text-[12px]">项目资产与任务产物将汇总于此</p>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right configuration rail ~322px */}
      <aside
        className="hidden w-[300px] shrink-0 flex-col border-l border-black/[0.06] bg-white lg:flex dark:border-border-light dark:bg-surface-primary"
        aria-label="项目配置"
      >
        <div className="border-b border-black/[0.06] px-4 py-3 text-[13px] font-semibold">
          项目配置
        </div>
        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {RAIL.map((item) => (
            <div
              key={item.id}
              className="rounded-xl border border-black/[0.06] bg-[#fafafa] p-3 dark:border-border-light dark:bg-surface-secondary"
            >
              <div className="mb-1 flex items-center justify-between">
                <span className="text-[13px] font-medium">{item.label}</span>
                <button
                  type="button"
                  className="rounded-md p-0.5 text-[#8c8c8c] hover:bg-black/[0.04]"
                  aria-label={`添加${item.label}`}
                  onClick={() => {
                    if (item.id === 'automation') {
                      navigate('/automation');
                    } else if (item.id === 'skill') {
                      navigate('/capability');
                    } else if (item.id === 'expert') {
                      navigate('/capability');
                    } else if (item.id === 'connector') {
                      navigate('/capability');
                    }
                  }}
                >
                  <Plus className="h-4 w-4" />
                </button>
              </div>
              <p className="text-[11.5px] leading-relaxed text-[#8c8c8c]">{item.hint}</p>
              {item.id === 'automation' ? (
                <button
                  type="button"
                  onClick={() => navigate('/automation')}
                  className="mt-2 flex w-full items-center gap-2 rounded-lg bg-white px-2 py-1.5 text-left text-[12px] ring-1 ring-black/[0.05]"
                >
                  <MessageSquare className="h-3.5 w-3.5 text-[#6b6b6b]" />
                  <span className="min-w-0 flex-1 truncate">管理定时任务</span>
                </button>
              ) : null}
            </div>
          ))}
        </div>
      </aside>
    </main>
  );
}
