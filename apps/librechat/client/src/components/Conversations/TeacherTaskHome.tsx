import React, { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertCircle, Clock3, ListTodo, MessageSquarePlus } from 'lucide-react';
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

function startOfLocalDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

function dayKey(task: PicoTask): string {
  const value = taskTimeValue(task);
  if (!value) {
    return '未知日期';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '未知日期';
  }
  const today = startOfLocalDay(new Date());
  const day = startOfLocalDay(date);
  const diffDays = Math.round((today - day) / 86_400_000);
  if (diffDays === 0) {
    return '今天';
  }
  if (diffDays === 1) {
    return '昨天';
  }
  if (diffDays === 2) {
    return '前天';
  }
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  }).format(date);
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

/** Teacher-readable failure line; never dump stacks/secrets. */
export function taskFailureHint(task: PicoTask): string | null {
  const run = task.latest_run;
  if (!run || run.status !== 'failed') {
    return null;
  }
  const raw = (run.error || '').trim();
  if (!raw) {
    return '任务未完成，可打开后重试。';
  }
  const low = raw.toLowerCase();
  if (low.includes('traceback') || raw.length > 120) {
    return '任务失败，请打开查看详情后重试。';
  }
  if (low.includes('token') || raw.includes('长度')) {
    return '可能因内容过长失败，请缩短后重试。';
  }
  if (low.includes('timeout') || raw.includes('超时')) {
    return '处理超时，请重试或把问题拆短。';
  }
  return raw.length > 80 ? `${raw.slice(0, 80)}…` : raw;
}

function TaskRow({ task, onOpen }: { task: PicoTask; onOpen: () => void }) {
  const navigate = useNavigate();
  const status = labelForLatestRun(task.latest_run) || '暂无运行';
  const time = formatTaskTime(task);
  const conversationId = task.conversation_id as string;
  const title = task.title?.trim() || '未命名任务';
  const href = `/c/${encodeURIComponent(conversationId)}`;
  const failHint = taskFailureHint(task);

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
          <Clock3 className="h-3 w-3 shrink-0" aria-hidden="true" />
          <span className="truncate">{time}</span>
        </p>
        {failHint ? (
          <p
            className="mt-0.5 truncate text-[11px] text-red-700 dark:text-red-300"
            data-testid="teacher-task-fail-hint"
            title={failHint}
          >
            {failHint}
          </p>
        ) : null}
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

export function groupTasksByDay(tasks: PicoTask[]): { day: string; tasks: PicoTask[] }[] {
  const sorted = [...tasks].sort((a, b) => {
    const ta = taskTimeValue(a) || '';
    const tb = taskTimeValue(b) || '';
    return tb.localeCompare(ta);
  });
  const map = new Map<string, PicoTask[]>();
  for (const task of sorted) {
    const key = dayKey(task);
    const list = map.get(key) || [];
    list.push(task);
    map.set(key, list);
  }
  return Array.from(map.entries()).map(([day, group]) => ({ day, tasks: group }));
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
  const groups = useMemo(() => groupTasksByDay(rows), [rows]);

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
      <div className="space-y-3" data-testid="teacher-task-day-groups">
        {groups.map(({ day, tasks: dayTasks }) => (
          <section key={day} aria-label={day}>
            <h3 className="sticky top-0 z-[1] bg-surface-primary/95 px-1 py-1 text-[11px] font-semibold uppercase tracking-wide text-text-secondary backdrop-blur-sm">
              {day}
            </h3>
            <div className="space-y-1">
              {dayTasks.map((task) => (
                <TaskRow key={task.id} task={task} onOpen={onOpen} />
              ))}
            </div>
          </section>
        ))}
      </div>
    );
  } else if (!error) {
    rowsContent = (
      <div
        className="flex flex-col items-center gap-3 px-3 py-8 text-center"
        role="status"
        data-testid="teacher-task-empty"
      >
        <p className="text-sm text-text-secondary">
          {localize('com_ui_pico_task_history_empty')}
        </p>
        <p className="max-w-[16rem] text-xs text-text-secondary">
          在下方输入框描述任务并发送，即可开始；完成后可在此按时间找回。
        </p>
        <Link
          to="/c/new"
          onClick={onOpen}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-surface-submit px-3 py-2 text-sm font-medium text-white hover:opacity-90"
          data-testid="teacher-task-empty-start"
        >
          <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
          开始新任务
        </Link>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-2" data-testid="teacher-task-home">
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
