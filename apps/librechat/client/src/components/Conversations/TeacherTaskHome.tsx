import React, { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Clock3, ListTodo } from 'lucide-react';
import { labelForLatestRun, type PicoTask } from '~/data-provider/pico/api';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

const STATUS_CLASS: Record<string, string> = {
  进行中: 'bg-blue-100 text-blue-800 dark:bg-blue-950 dark:text-blue-200',
  停止中: 'bg-amber-100 text-amber-900 dark:bg-amber-950 dark:text-amber-100',
  失败: 'bg-red-100 text-red-800 dark:bg-red-950 dark:text-red-200',
  已停止: 'bg-surface-tertiary text-text-secondary',
  已完成: 'bg-emerald-50 text-emerald-800 dark:bg-emerald-950 dark:text-emerald-200',
};

export function recoverableTasks(tasks: PicoTask[]): PicoTask[] {
  return tasks.filter((task) => Boolean(task.conversation_id));
}

export function taskTimeValue(task: PicoTask): string | null {
  return task.latest_run?.ended_at || task.latest_run?.started_at || task.created_at || null;
}

function formatTaskTime(task: PicoTask): string {
  const value = taskTimeValue(task);
  if (!value) {
    return '时间未知';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '时间未知';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function TaskRow({ task, onOpen }: { task: PicoTask; onOpen: () => void }) {
  const navigate = useNavigate();
  const status = labelForLatestRun(task.latest_run) || '暂无运行';
  const time = formatTaskTime(task);
  const conversationId = task.conversation_id as string;
  const title = task.title?.trim() || '未命名任务';
  const href = `/c/${encodeURIComponent(conversationId)}`;

  return (
    <Link
      to={href}
      onClick={(event) => {
        event.preventDefault();
        onOpen();
        navigate(href);
      }}
      className="group flex min-h-14 items-center gap-2 rounded-lg px-2 py-2 outline-none hover:bg-surface-active-alt focus-visible:ring-2 focus-visible:ring-black dark:focus-visible:ring-white"
      aria-label={`${title}，${status}，${time}`}
      data-testid="teacher-task-row"
    >
      <ListTodo className="h-4 w-4 shrink-0 text-text-secondary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-text-primary" title={title}>
          {title}
        </p>
        <p className="mt-0.5 flex items-center gap-1 text-[11px] text-text-secondary">
          <Clock3 className="h-3 w-3" aria-hidden="true" />
          <span>{time}</span>
        </p>
      </div>
      <span
        className={cn(
          'shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none',
          STATUS_CLASS[status] || 'bg-surface-tertiary text-text-secondary',
        )}
        data-testid="teacher-task-status"
      >
        {status}
      </span>
    </Link>
  );
}

export default function TeacherTaskHome({
  tasks,
  loading,
  error,
  onRetry,
  onOpen,
}: {
  tasks: PicoTask[];
  loading: boolean;
  error: string | null;
  onRetry: () => void;
  onOpen: () => void;
}) {
  const localize = useLocalize();
  const rows = useMemo(() => recoverableTasks(tasks), [tasks]);

  if (loading && rows.length === 0) {
    return (
      <div
        className="flex flex-1 items-center justify-center px-4 text-sm text-text-secondary"
        role="status"
      >
        {localize('com_ui_pico_task_history_loading')}
      </div>
    );
  }

  let rowsContent: React.ReactNode = null;
  if (rows.length > 0) {
    rowsContent = (
      <div className="space-y-1">
        {rows.map((task) => (
          <TaskRow key={task.id} task={task} onOpen={onOpen} />
        ))}
      </div>
    );
  } else if (!error) {
    rowsContent = (
      <div className="py-8 text-center text-sm text-text-secondary" role="status">
        {localize('com_ui_pico_task_history_empty')}
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-2" data-testid="teacher-task-home">
      {error ? (
        <div
          className="mb-2 flex items-center gap-2 rounded-lg bg-red-50 px-2 py-2 text-xs text-red-800 dark:bg-red-950 dark:text-red-200"
          role="alert"
        >
          <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="min-w-0 flex-1">{error}</span>
          <button
            type="button"
            className="shrink-0 rounded px-1.5 py-1 font-medium hover:bg-black/5 dark:hover:bg-white/10"
            onClick={onRetry}
          >
            {localize('com_ui_retry')}
          </button>
        </div>
      ) : null}
      {rowsContent}
    </div>
  );
}
