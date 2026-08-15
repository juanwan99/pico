/**
 * Zoom controls for html preview + sandbox webpage screenshot.
 * Buttons and ctrl/⌘+wheel; current ratio is always visible.
 */
import { useCallback, useState } from 'react';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  clampResultPaneZoom,
  formatResultPaneZoom,
  RESULT_PANE_ZOOM_STEP,
} from '~/utils/picoOpenInPane';

export function usePaneZoom(initial = 1) {
  const [zoom, setZoom] = useState(initial);
  const zoomIn = useCallback(
    () => setZoom((value) => clampResultPaneZoom(value + RESULT_PANE_ZOOM_STEP)),
    [],
  );
  const zoomOut = useCallback(
    () => setZoom((value) => clampResultPaneZoom(value - RESULT_PANE_ZOOM_STEP)),
    [],
  );
  const reset = useCallback(() => setZoom(1), []);
  const onWheel = useCallback((event: React.WheelEvent) => {
    if (!event.ctrlKey && !event.metaKey) {
      return;
    }
    event.preventDefault();
    const delta = event.deltaY > 0 ? -RESULT_PANE_ZOOM_STEP : RESULT_PANE_ZOOM_STEP;
    setZoom((value) => clampResultPaneZoom(value + delta));
  }, []);
  return {
    zoom,
    label: formatResultPaneZoom(zoom),
    zoomIn,
    zoomOut,
    reset,
    onWheel,
  };
}

export default function PaneZoomBar({
  label,
  zoomIn,
  zoomOut,
  reset,
}: {
  label: string;
  zoomIn: () => void;
  zoomOut: () => void;
  reset: () => void;
}) {
  return (
    <div
      className="inline-flex items-center rounded-md border border-black/[0.08] bg-white dark:border-border-light dark:bg-surface-secondary"
      data-testid="pane-zoom-bar"
      data-zoom={label}
    >
      <button
        type="button"
        className="rounded-l-md p-1 text-[#6b6b6b] hover:bg-black/[0.04]"
        aria-label="缩小"
        title="缩小"
        data-testid="pane-zoom-out"
        onClick={zoomOut}
      >
        <PicoIcon name="zoom-out" size="sm" />
      </button>
      <button
        type="button"
        className="pico-type-aux pico-type-medium min-w-[2.75rem] px-1 text-center tabular-nums text-[#3d3d3d] hover:bg-black/[0.04] dark:text-text-primary"
        aria-label="重置缩放"
        title="重置为 100%"
        data-testid="pane-zoom-label"
        onClick={reset}
      >
        {label}
      </button>
      <button
        type="button"
        className="rounded-r-md p-1 text-[#6b6b6b] hover:bg-black/[0.04]"
        aria-label="放大"
        title="放大"
        data-testid="pane-zoom-in"
        onClick={zoomIn}
      >
        <PicoIcon name="zoom-in" size="sm" />
      </button>
    </div>
  );
}
