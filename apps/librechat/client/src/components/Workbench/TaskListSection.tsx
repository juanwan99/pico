/**
 * Left-rail task list (WorkBuddy-class): 任务 (n) + recent conversations.
 */
import { memo, useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Loader2 } from 'lucide-react';
import type { ConversationListResponse, TConversation } from 'librechat-data-provider';
import { useConversationsInfiniteQuery } from '~/data-provider';
import { useAuthContext } from '~/hooks';
import { cn } from '~/utils';

function relativeTime(iso?: string | Date | null): string {
  if (!iso) {
    return '';
  }
  const t = typeof iso === 'string' ? Date.parse(iso) : iso.getTime();
  if (Number.isNaN(t)) {
    return '';
  }
  const sec = Math.max(0, Math.floor((Date.now() - t) / 1000));
  if (sec < 60) {
    return '刚刚';
  }
  if (sec < 3600) {
    return `${Math.floor(sec / 60)}分钟前`;
  }
  if (sec < 86400) {
    return `${Math.floor(sec / 3600)}小时前`;
  }
  if (sec < 86400 * 30) {
    return `${Math.floor(sec / 86400)}天前`;
  }
  return `${Math.floor(sec / (86400 * 30))}个月前`;
}

function TaskListSection() {
  const navigate = useNavigate();
  const { conversationId: routeId } = useParams();
  const { isAuthenticated } = useAuthContext();

  const { data, isLoading } = useConversationsInfiniteQuery(
    { sortBy: 'updatedAt', sortDirection: 'desc' },
    {
      enabled: isAuthenticated,
      staleTime: 15000,
      cacheTime: 300000,
    },
  );

  const conversations = useMemo(() => {
    const list = data?.pages.flatMap((p: ConversationListResponse) => p.conversations) ?? [];
    return list.slice(0, 40) as TConversation[];
  }, [data?.pages]);

  const count = conversations.length;

  return (
    <div className="mt-3 min-h-0 flex-1 border-t border-black/[0.05] pt-3" data-testid="task-list">
      <div className="mb-1 flex items-center justify-between px-2.5">
        <span className="text-[12px] font-medium text-[#6b6b6b]">任务 ({count})</span>
        {isLoading ? <Loader2 className="h-3 w-3 animate-spin text-[#9a9a9a]" /> : null}
      </div>
      <ul className="max-h-[42vh] space-y-0.5 overflow-y-auto px-1.5 pb-2">
        {conversations.length === 0 && !isLoading ? (
          <li className="px-2 py-3 text-center text-[12px] text-[#9a9a9a]">暂无任务</li>
        ) : null}
        {conversations.map((c) => {
          const id = c.conversationId ?? '';
          const active = routeId === id;
          const title =
            c.title && c.title !== 'New Chat' && c.title !== '新对话' ? c.title : '未命名任务';
          return (
            <li key={id || Math.random()}>
              <button
                type="button"
                onClick={() => id && navigate(`/c/${id}`)}
                className={cn(
                  'flex w-full flex-col gap-0.5 rounded-[10px] px-2.5 py-2 text-left transition-colors',
                  active
                    ? 'bg-[#e6e6e6] dark:bg-surface-tertiary'
                    : 'hover:bg-[#e8e8e8] dark:hover:bg-surface-hover',
                )}
              >
                <div className="flex items-start gap-2">
                  <span
                    className={cn(
                      'mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full',
                      active ? 'bg-[#1a1a1a]' : 'bg-[#c8c8c8]',
                    )}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <span className="line-clamp-2 text-[12.5px] font-medium leading-snug text-[#1a1a1a] dark:text-text-primary">
                      {title}
                    </span>
                    <span className="mt-0.5 block text-[11px] text-[#9a9a9a]">
                      {relativeTime(c.updatedAt as string | undefined)}
                    </span>
                  </div>
                </div>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default memo(TaskListSection);
