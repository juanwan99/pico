import { Loader2 } from 'lucide-react';
import clsx from 'clsx';

export default function RunLoadingIndicator({
  label = '等待模型响应',
  className,
  spin = true,
}: {
  label?: string;
  className?: string;
  spin?: boolean;
}) {
  return (
    <span
      role="status"
      aria-live="polite"
      className={clsx('inline-flex items-center gap-1.5', className)}
    >
      {spin ? (
        <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin" aria-hidden="true" />
      ) : null}
      {label}
    </span>
  );
}
