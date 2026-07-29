/**
 * Center column run status strip: 等待模型响应 / 已完成 etc.
 */
import { memo } from 'react';
import { Loader2, CheckCircle2 } from 'lucide-react';
import { cn } from '~/utils';

function TaskRunBar({
  title,
  isSubmitting,
  completedLabel,
}: {
  title?: string | null;
  isSubmitting: boolean;
  completedLabel?: string | null;
}) {
  const displayTitle =
    title && title !== 'New Chat' && title !== '新对话' ? title : '当前任务';

  return (
    <div
      className="flex items-center gap-2 border-b border-black/[0.05] bg-white/90 px-3 py-2 backdrop-blur-sm dark:border-border-light dark:bg-surface-primary/90"
      data-testid="task-run-bar"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-[#1a1a1a] dark:text-text-primary">
          {displayTitle}
        </p>
      </div>
      {isSubmitting ? (
        <span className="inline-flex items-center gap-1.5 rounded-full bg-[#edf1f4] px-2.5 py-1 text-[12px] font-medium text-[#3d3d3d]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          等待模型响应
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
