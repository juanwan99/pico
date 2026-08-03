/**
 * Center column run status strip: 等待模型响应 / 已完成 + model/duration.
 */
import { memo } from 'react';
import { AlertCircle, CheckCircle2, RotateCcw, Square } from 'lucide-react';
import { cn } from '~/utils';
import RunLoadingIndicator from './RunLoadingIndicator';

function TaskRunBar({
  title,
  isSubmitting,
  completedLabel,
  model,
  statusLabel,
  canCancel,
  cancelling,
  onCancel,
  canRerun,
  rerunning,
  onRerun,
  processHint,
}: {
  title?: string | null;
  isSubmitting: boolean;
  completedLabel?: string | null;
  model?: string | null;
  statusLabel?: string | null;
  processHint?: string | null;
  canCancel?: boolean;
  cancelling?: boolean;
  onCancel?: () => void;
  canRerun?: boolean;
  rerunning?: boolean;
  onRerun?: () => void;
}) {
  const displayTitle = title && title !== 'New Chat' && title !== '新对话' ? title : '当前任务';
  const failed = Boolean(statusLabel?.startsWith('失败') || completedLabel?.startsWith('失败'));
  const cancelled = Boolean(
    statusLabel?.startsWith('已停止') ||
      completedLabel?.startsWith('已停止') ||
      statusLabel?.startsWith('已取消') ||
      completedLabel?.startsWith('已取消'),
  );
  const rerunLabel = rerunning ? '重新运行中' : '重新运行';

  return (
    <div
      className="dark:bg-surface-primary/90 relative z-20 mt-[52px] flex min-h-11 shrink-0 items-center gap-2 overflow-hidden border-b border-black/[0.06] bg-white px-3 py-1 dark:border-border-light sm:px-4"
      data-testid="task-run-bar"
    >
      <div className="min-w-0 flex-1 overflow-hidden">
        <p className="truncate text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary">
          {displayTitle}
        </p>
        {model ? <p className="truncate text-[11px] text-[#8c8c8c]">模型 {model}</p> : null}
        {processHint ? (
          <p className="truncate text-[11px] text-[#3b6fd9]" data-testid="task-process-hint">
            {processHint}
          </p>
        ) : null}
      </div>
      {canCancel ? (
        <>
          <RunLoadingIndicator className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d]" />
          <button
            type="button"
            data-testid="task-stop-button"
            className="inline-flex items-center gap-1 rounded-full border border-black/[0.08] bg-white px-2.5 py-1 text-[12px] font-medium text-[#6b3f3f] hover:bg-[#fdeeee] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-surface-secondary"
            onClick={onCancel}
            disabled={cancelling}
            aria-busy={cancelling || undefined}
          >
            <Square className="h-3 w-3 fill-current" />
            {cancelling ? '停止中' : '停止'}
          </button>
        </>
      ) : isSubmitting ? (
        <RunLoadingIndicator className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d]" />
      ) : failed ? (
        <div className="flex min-w-0 items-center gap-2">
          <span className="inline-flex min-w-0 max-w-[240px] items-center gap-1.5 rounded-full bg-[#fdeeee] px-2.5 py-1 text-[12px] font-medium text-[#9a3b3b]">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            <span className="truncate">{completedLabel || statusLabel || '失败'}</span>
          </span>
          {canRerun && (
            <button
              type="button"
              data-testid="task-rerun-button"
              className="inline-flex shrink-0 items-center gap-1 rounded-full border border-black/[0.08] bg-white px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d] hover:bg-[#f3f3f3] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-surface-secondary"
              onClick={onRerun}
              disabled={rerunning}
              aria-busy={rerunning || undefined}
            >
              <RotateCcw className="h-3 w-3" />
              {rerunLabel}
            </button>
          )}
        </div>
      ) : cancelled ? (
        <span className="inline-flex max-w-[50%] items-center gap-1.5 rounded-full bg-[#f3f3f3] px-2.5 py-1 text-[12px] font-medium text-[#6b6b6b]">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{completedLabel || statusLabel || '已停止'}</span>
        </span>
      ) : completedLabel ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#eef7ee] px-2.5 py-1 text-[12px] font-medium text-[#2d6a3e]">
          <CheckCircle2 className="h-3.5 w-3.5" />
          {completedLabel}
        </span>
      ) : (
        <span
          className={cn(
            'inline-flex items-center rounded-full bg-[#f3f3f3] px-2.5 py-1 text-[12px] text-[#6b6b6b]',
          )}
        >
          就绪
        </span>
      )}
    </div>
  );
}

export default memo(TaskRunBar);
