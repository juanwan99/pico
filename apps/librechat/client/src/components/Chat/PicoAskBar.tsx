/**
 * Human-path ask card. ResultPanel RunTimeline keeps engineer copy only;
 * teachers must not open 结果区 to unstick a parked turn.
 */
import { useState } from 'react';
import { CheckCircle2, Circle } from 'lucide-react';
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
  const [error, setError] = useState<string | null>(null);
  const ask = liveAskForRun(run, events);
  if (!ask || !run?.id) {
    return null;
  }

  const pick = (label: string) => {
    if (busyOption) {
      return;
    }
    setError(null);
    setBusyOption(label);
    void answerPicoAsk(run.id, label).catch(() => {
      setBusyOption(null);
      setError('没送出去，再点一次');
    });
  };

  return (
    <div
      className="mb-3 rounded-2xl border-2 border-[#3b6fd9] bg-white px-3 py-3 shadow-[0_1px_0_rgba(59,111,217,0.12)] dark:border-[#3b6fd9]/70 dark:bg-surface-secondary"
      data-testid="pico-ask-main"
      role="group"
      aria-label={ask.question}
    >
      <p className="text-[11px] font-semibold tracking-wide text-[#3b6fd9]">需要你选一项</p>
      <p className="mt-1 text-[15px] font-semibold leading-snug text-[#1a3a7a] dark:text-text-primary">
        {ask.question}
      </p>
      <p className="mt-1 text-[12px] text-[#6b6b6b] dark:text-text-secondary">
        点一项继续。这时不是在跑模型。
      </p>
      <div className="mt-3 flex flex-col gap-2" role="listbox" aria-label="选项">
        {ask.options.map((label) => {
          const selected = busyOption === label;
          const dimmed = Boolean(busyOption) && !selected;
          return (
            <button
              key={label}
              type="button"
              data-testid="pico-ask-option"
              aria-pressed={selected}
              disabled={Boolean(busyOption)}
              onClick={() => pick(label)}
              className={[
                'flex w-full items-start gap-2.5 rounded-xl border px-3 py-2.5 text-left text-[13px] leading-snug transition-colors',
                selected
                  ? 'border-[#3b6fd9] bg-[#e8f1ff] text-[#1a3a7a] dark:bg-[#1a2a4a] dark:text-text-primary'
                  : 'border-black/10 bg-white text-[#1f1f1f] hover:border-[#3b6fd9]/50 hover:bg-[#f5f9ff] dark:border-border-light dark:bg-surface-primary dark:text-text-primary',
                dimmed ? 'opacity-40' : '',
                'disabled:cursor-wait',
              ].join(' ')}
            >
              {selected ? (
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-[#3b6fd9]" aria-hidden="true" />
              ) : (
                <Circle className="mt-0.5 h-4 w-4 shrink-0 text-[#9aa7c2]" aria-hidden="true" />
              )}
              <span>{label}</span>
            </button>
          );
        })}
      </div>
      {busyOption ? (
        <p className="mt-2 text-[12px] font-medium text-[#3b6fd9]" data-testid="pico-ask-busy">
          已选「{busyOption}」· 继续中…
        </p>
      ) : null}
      {error ? (
        <p className="mt-2 text-[12px] font-medium text-[#9a3b3b]" data-testid="pico-ask-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
