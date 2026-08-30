import { formatComposerQuote } from '~/hooks/Pico/formatPointsLabel';
import { usePointsMeter } from '~/hooks/Pico/usePointsMeter';

/** Live 预计 above the composer for the in-flight turn only. */
export default function PointsBar() {
  const { composerLive, points } = usePointsMeter();
  const label = formatComposerQuote(composerLive, points);
  if (!label) {
    return null;
  }
  return (
    <div
      className="mb-1.5 flex w-full justify-end px-1"
      data-testid="pico-points-bar"
      aria-live="polite"
    >
      <span className="pico-type-aux text-[12px] text-[color:var(--pico-ink-3)]">{label}</span>
    </div>
  );
}
