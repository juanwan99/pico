import { memo } from 'react';
import { TooltipAnchor } from '@librechat/client';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useLocalize } from '~/hooks';
import { cn } from '~/utils';

export default memo(function StopButton({
  stop,
  setShowStopButton,
}: {
  stop: (e: React.MouseEvent<HTMLButtonElement>) => void;
  setShowStopButton: (value: boolean) => void;
}) {
  const localize = useLocalize();

  // Distinct from task-bar「停止任务」(ledger cancel). This only aborts the
  // client stream / screen output; durable Pico runs may keep finishing.
  const stopLabel = localize('com_nav_stop_generating');

  return (
    <TooltipAnchor
      description={stopLabel}
      render={
        <button
          type="button"
          data-testid="stop-generation-button"
          title={stopLabel}
          className={cn(
            'inline-flex h-8 w-8 items-center justify-center rounded-md text-[color:var(--pico-ink)] outline-offset-4 transition-colors hover:bg-black/[0.04] disabled:cursor-not-allowed disabled:opacity-40',
          )}
          aria-label={stopLabel}
          onClick={(e) => {
            setShowStopButton(false);
            stop(e);
          }}
        >
          <PicoIcon name="stop" />
        </button>
      }
    ></TooltipAnchor>
  );
});
