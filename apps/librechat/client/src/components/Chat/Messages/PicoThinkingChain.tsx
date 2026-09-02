import { useMemo, useState, type MouseEvent } from 'react';
import { cn } from '~/utils';

/**
 * Pico thinking chain under the assistant header.
 * Default: at most 3 lines. Click expands to a scrollable block.
 * Never the product bubble.
 */
export default function PicoThinkingChain({
  text,
  isSubmitting = false,
}: {
  text?: string | null;
  isSubmitting?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const body = (text ?? '').trim();
  const display = body || (isSubmitting ? '正在思考…' : '');

  const canExpand = useMemo(() => {
    if (!body) {
      return false;
    }
    return body.split('\n').length > 3 || body.length > 160;
  }, [body]);

  if (!display) {
    return null;
  }

  const onToggle = (event: MouseEvent<HTMLButtonElement>) => {
    event.preventDefault();
    if (canExpand) {
      setExpanded((prev) => !prev);
    }
  };

  const label = isSubmitting && !body ? '正在思考' : '思考过程';

  return (
    <button
      type="button"
      data-testid="pico-thinking-chain"
      data-expanded={expanded ? 'true' : 'false'}
      data-submitting={isSubmitting ? 'true' : 'false'}
      aria-expanded={canExpand ? expanded : undefined}
      onClick={onToggle}
      className={cn(
        'mb-1 w-full rounded-md py-0.5 text-left text-[12px] leading-5 text-[#8c8c8c]',
        canExpand ? 'cursor-pointer hover:text-[#5c5c5c]' : 'cursor-default',
      )}
    >
      <span className="mb-0.5 block text-[11px] font-medium tracking-wide text-[#a3a3a3]">
        {label}
        {canExpand ? (expanded ? ' · 收起' : ' · 展开') : ''}
      </span>
      <span
        data-testid="pico-thinking-chain-body"
        className={cn(
          'block whitespace-pre-wrap break-words',
          expanded ? 'max-h-48 overflow-y-auto' : 'line-clamp-3',
        )}
      >
        {display}
      </span>
    </button>
  );
}
