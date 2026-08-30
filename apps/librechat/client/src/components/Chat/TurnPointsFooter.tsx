import { formatTurnPointsLabel } from '~/hooks/Pico/formatPointsLabel';
import { usePointsMeter } from '~/hooks/Pico/usePointsMeter';

/** Pins this round's 预计/实际 at the end of the assistant reply. Never cleared. */
export default function TurnPointsFooter({
  messageId,
  isCreatedByUser,
}: {
  messageId?: string | null;
  isCreatedByUser?: boolean;
}) {
  const { turnForMessage } = usePointsMeter();
  if (isCreatedByUser) {
    return null;
  }
  const label = formatTurnPointsLabel(turnForMessage(messageId));
  if (!label) {
    return null;
  }
  return (
    <div
      className="mt-1 flex w-full justify-end px-0.5"
      data-testid="pico-turn-points"
      data-message-id={messageId ?? ''}
    >
      <span className="pico-type-aux text-[12px] text-[color:var(--pico-ink-3)]">{label}</span>
    </div>
  );
}
