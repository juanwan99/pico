/**
 * Center column run status strip: 等待模型响应 / 已完成 + model/duration.
 */
import { memo } from 'react';
import { AlertCircle, CheckCircle2, Square } from 'lucide-react';
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
}: {
  title?: string | null;
  isSubmitting: boolean;
  completedLabel?: string | null;
  model?: string | null;
  statusLabel?: string | null;
  canCancel?: boolean;
  cancelling?: boolean;
  onCancel?: () => void;
}) {
  const displayTitle = title && title !== 'New Chat' && title !== '新对话' ? title : '当前任务';
  const failed = Boolean(statusLabel?.startsWith('失败') || completedLabel?.startsWith('失败'));
  const cancelled = Boolean(
    statusLabel?.startsWith('已取消') || completedLabel?.startsWith('已取消'),
  );

  return (
    <div
      className="dark:bg-surface-primary/90 flex h-11 items-center gap-2 border-b border-black/[0.06] bg-white px-4 py-0 dark:border-border-light"
      data-testid="task-run-bar"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary">
          {displayTitle}
        </p>
        {model ? <p className="truncate text-[11px] text-[#8c8c8c]">模型 {model}</p> : null}
      </div>
      {canCancel ? (
        <>
          <RunLoadingIndicator className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d]" />
          <button
            type="button"
            className="inline-flex items-center gap-1 rounded-full border border-black/[0.08] bg-white px-2.5 py-1 text-[12px] font-medium text-[#6b3f3f] hover:bg-[#fdeeee] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-surface-secondary"
            onClick={onCancel}
            disabled={cancelling}
          >
            <Square className="h-3 w-3 fill-current" />
            {cancelling ? '停止中' : '停止'}
          </button>
        </>
      ) : isSubmitting ? (
        <RunLoadingIndicator className="rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d]" />
      ) : failed ? (
        <span className="inline-flex max-w-[50%] items-center gap-1.5 rounded-full bg-[#fdeeee] px-2.5 py-1 text-[12px] font-medium text-[#9a3b3b]">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{completedLabel || statusLabel || '失败'}</span>
        </span>
      ) : cancelled ? (
        <span className="inline-flex max-w-[50%] items-center gap-1.5 rounded-full bg-[#f3f3f3] px-2.5 py-1 text-[12px] font-medium text-[#6b6b6b]">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span className="truncate">{completedLabel || statusLabel || '已取消'}</span>
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
