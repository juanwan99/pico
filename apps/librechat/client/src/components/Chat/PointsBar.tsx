import { formatPointsLabel } from '~/hooks/Pico/formatPointsLabel';
import { usePointsMeter } from '~/hooks/Pico/usePointsMeter';

export default function PointsBar() {
  const { phase, points } = usePointsMeter();
  const label = formatPointsLabel(phase, points);
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
