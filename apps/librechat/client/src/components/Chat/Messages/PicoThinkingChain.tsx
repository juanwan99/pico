import { useState, type MouseEvent } from 'react';
import { usePicoRunSteps } from '~/hooks/Pico/PicoRunStepsContext';

/** Thinking text only reaches the teacher when it is mostly Chinese (#1169). */
export function isMostlyChinese(text: string): boolean {
  const han = (text.match(/[\u3400-\u9fff]/g) ?? []).length;
  const latin = (text.match(/[A-Za-z]/g) ?? []).length;
  return han > 0 && han >= latin;
}

/**
 * Pico process box under the assistant header. Never the product bubble.
 * While the run goes: a fixed 4-line window, newest step at the bottom,
 * older lines slide up and out (#1169). After: one「处理过程」line that
 * expands to every step.
 */
export default function PicoThinkingChain({
  text,
  isSubmitting = false,
  withRunSteps = false,
}: {
  text?: string | null;
  isSubmitting?: boolean;
  /** Latest reply: show the ledger's step lines for its run. */
  withRunSteps?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const runSteps = usePicoRunSteps();
  // Right after send the ledger still holds the previous run until the new one starts.
  const steps = withRunSteps && (!isSubmitting || runSteps.active) ? runSteps.lines : [];
  const think = (text ?? '').trim();
  const lines = steps.map((line) => `▸ ${line}`);
  if (isMostlyChinese(think)) {
    lines.push(think);
  }

  if (isSubmitting) {
    return (
      <div
        data-testid="pico-thinking-chain"
        data-submitting="true"
        className="mb-1 w-full py-0.5 text-[12px] leading-5 text-[#8c8c8c]"
      >
        <span className="mb-0.5 block text-[11px] font-medium tracking-wide text-[#a3a3a3]">
          {lines.length ? '正在处理' : '正在思考'}
        </span>
        <div
          data-testid="pico-thinking-chain-body"
          className="flex h-20 flex-col justify-end overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,black_40%)]"
        >
          {lines.length ? (
            lines.slice(-8).map((line, idx) => (
              <span key={idx} className="block whitespace-pre-wrap break-words">
                {line}
              </span>
            ))
          ) : (
            <span className="block">正在思考…</span>
          )}
        </div>
      </div>
    );
  }

  if (!lines.length) {
    return null;
  }

  const onToggle = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    setExpanded((prev) => !prev);
  };

  return (
    <button
      type="button"
      data-testid="pico-thinking-chain"
      data-expanded={expanded ? 'true' : 'false'}
      data-submitting="false"
      aria-expanded={expanded}
      onClick={onToggle}
      className="mb-1 w-full cursor-pointer rounded-md py-0.5 text-left text-[12px] leading-5 text-[#8c8c8c] hover:text-[#5c5c5c]"
    >
      <span className="block text-[11px] font-medium tracking-wide text-[#a3a3a3]">
        处理过程{steps.length ? ` · ${steps.length} 步` : ''}
        {expanded ? ' · 收起' : ' · 展开'}
      </span>
      {expanded ? (
        <span
          data-testid="pico-thinking-chain-body"
          className="mt-0.5 block max-h-48 overflow-y-auto whitespace-pre-wrap break-words"
        >
          {lines.join('\n')}
        </span>
      ) : null}
    </button>
  );
}
