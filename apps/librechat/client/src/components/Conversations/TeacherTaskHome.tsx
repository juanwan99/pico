import React, { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { humanizeRunError, labelForLatestRun, type PicoTask } from '~/data-provider/pico/api';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

const STATUS_CLASS: Record<string, string> = {
  进行中: 'bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]',
  '仍在处理…': 'bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]',
  停止中: 'bg-[color:var(--pico-amber-wash)] text-[color:var(--pico-amber)]',
  失败: 'bg-[color:var(--pico-red-wash)] text-[color:var(--pico-red)]',
  已停止: 'bg-[color:var(--pico-surface-2)] text-[color:var(--pico-ink-2)]',
  已完成: 'bg-[color:var(--pico-mint-wash)] text-[color:var(--pico-mint-dark)]',
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
  const mapped = humanizeRunError(run.error, run.user_message ?? null);
  if (mapped) {
    return mapped.length > 80 ? `${mapped.slice(0, 80)}…` : mapped;
  }
  return '任务未完成，可打开后重试。';
}

export function iconForTaskStatus(status: string): {
  name: PicoIconName;
  className: string;
} {
  if (status === '已完成') {
    return { name: 'check', className: 'text-[color:var(--pico-mint-dark)]' };
  }
  if (status === '失败') {
    return { name: 'help', className: 'text-[color:var(--pico-red)]' };
  }
  if (status === '进行中' || status === '仍在处理…' || status === '停止中') {
    return { name: 'clock', className: 'text-[color:var(--pico-violet)]' };
  }
  return { name: 'doc', className: 'text-[color:var(--pico-ink-3)]' };
}

function TaskRow({ task, onOpen }: { task: PicoTask; onOpen: () => void }) {
  const navigate = useNavigate();
  const status = labelForLatestRun(task.latest_run) || '暂无运行';
  const time = formatTaskTime(task);
  const conversationId = task.conversation_id as string;
  const title = task.title?.trim() || '未命名任务';
  const href = `/c/${encodeURIComponent(conversationId)}`;
  const failHint = taskFailureHint(task);
  const taskIcon = iconForTaskStatus(status);

  return (
    <Link
      to={href}
      onClick={(event) => {
        event.preventDefault();
        onOpen();
        navigate(href);
      }}
      className="group grid min-h-14 min-w-0 grid-cols-[1rem_minmax(0,1fr)] items-start gap-2 rounded-xl px-2 py-2 outline-none hover:bg-[color:var(--pico-surface-2)] focus-visible:ring-2 focus-visible:ring-[color:var(--pico-violet)]"
      aria-label={`${title}，${status}，${time}`}
      data-testid="teacher-task-row"
    >
      <PicoIcon
        name={taskIcon.name}
        size="sm"
        className={cn('mt-0.5', taskIcon.className)}
        title={`${status}图标`}
      />
      <div className="min-w-0 flex-1">
        <p
          className="block min-w-0 truncate text-sm font-medium text-[color:var(--pico-ink)]"
          title={title}
          data-testid="teacher-task-title"
        >
          {title}
        </p>
        <div className="mt-1 flex min-w-0 items-center gap-1.5 text-[11px] text-[color:var(--pico-ink-3)]">
          <PicoIcon name="clock" size="sm" className="h-3 w-3" />
          <span className="min-w-0 flex-1 truncate">{time}</span>
          <span
            className={cn(
              'max-w-[4.5rem] shrink-0 truncate rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none',
              STATUS_CLASS[status] ||
                'bg-[color:var(--pico-surface-2)] text-[color:var(--pico-ink-2)]',
            )}
            data-testid="teacher-task-status"
          >
            {status}
          </span>
        </div>
        {failHint ? (
          <p
            className="mt-1 block min-w-0 truncate text-[11px] text-[color:var(--pico-red)]"
            data-testid="teacher-task-fail-hint"
            title={failHint}
          >
            {failHint}
          </p>
        ) : null}
      </div>
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
            <h3 className="sticky top-0 z-[1] bg-[color:var(--pico-sidebar)] px-1 py-1 text-[11px] font-semibold uppercase tracking-wide text-[color:var(--pico-ink-3)]">
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
        <p className="text-sm text-text-secondary">{localize('com_ui_pico_task_history_empty')}</p>
        <p className="max-w-[16rem] text-xs text-text-secondary">
          在下方输入框描述任务并发送，即可开始；完成后可在此按时间找回。
        </p>
        <Link
          to="/c/new"
          onClick={onOpen}
          className="inline-flex min-h-10 items-center gap-1.5 rounded-lg bg-surface-submit px-3 py-2 text-sm font-medium text-white hover:opacity-90"
          data-testid="teacher-task-empty-start"
        >
          <PicoIcon name="plus" size="sm" />
          开始新任务
        </Link>
      </div>
    );
  }

  return (
    <div
      className="min-h-0 min-w-0 flex-1 overflow-y-auto overflow-x-hidden px-3 pb-2"
      data-testid="teacher-task-home"
    >
      {error ? (
        <div
          className="mb-2 flex items-center gap-2 rounded-xl bg-[color:var(--pico-red-wash)] px-2 py-2 text-xs text-[color:var(--pico-red)]"
          role="alert"
        >
          <PicoIcon name="help" size="sm" />
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
