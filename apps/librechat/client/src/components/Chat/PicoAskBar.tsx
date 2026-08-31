/**
 * Human-path ask chips. ResultPanel RunTimeline keeps the engineer copy;
 * teachers must not open 结果区 to unstick a parked turn.
 */
import { useState } from 'react';
import { answerPicoAsk, type PicoRun, type PicoRunEvent } from '~/data-provider/pico/api';
import { liveAskForRun } from '~/utils/picoAskPrompt';

export default function PicoAskBar({
  run,
  events,
}: {
  run?: PicoRun | null;
  events?: PicoRunEvent[] | null;
}) {
  const [busyOption, setBusyOption] = useState<string | null>(null);
  const ask = liveAskForRun(run, events);
  if (!ask || !run?.id) {
    return null;
  }

  const pick = (label: string) => {
    if (busyOption) {
      return;
    }
    setBusyOption(label);
    void answerPicoAsk(run.id, label).catch(() => {
      setBusyOption(null);
    });
  };

  return (
    <div
      className="mb-2 rounded-xl border border-[#cfe0ff] bg-[#f5f9ff] px-3 py-2.5 dark:border-border-light dark:bg-surface-secondary"
      data-testid="pico-ask-main"
      role="group"
      aria-label={ask.question}
    >
      <p className="text-[13px] font-medium text-[#1a3a7a] dark:text-text-primary">{ask.question}</p>
      <p className="mt-0.5 text-[11px] text-[#6b6b6b] dark:text-text-secondary">点一项继续，不是还在跑</p>
      <div className="mt-2 flex flex-wrap gap-1.5">
        {ask.options.map((label) => (
          <button
            key={label}
            type="button"
            data-testid="pico-ask-option"
            disabled={Boolean(busyOption)}
            onClick={() => pick(label)}
            className="rounded-md border border-black/10 bg-white px-2.5 py-1.5 text-[13px] text-[#1f1f1f] hover:bg-[#f0f0f0] disabled:opacity-50 dark:border-border-light dark:bg-surface-primary dark:text-text-primary"
          >
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}
