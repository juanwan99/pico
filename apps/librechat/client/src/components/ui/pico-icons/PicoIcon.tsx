import { cn } from '~/utils';

export type PicoIconName =
  | 'home'
  | 'grid'
  | 'apps'
  | 'message'
  | 'file'
  | 'pen'
  | 'chart'
  | 'search'
  | 'clock'
  | 'check'
  | 'plus'
  | 'folder'
  | 'spark'
  | 'send'
  | 'arrow'
  | 'user'
  | 'logout'
  | 'link'
  | 'shield'
  | 'mic'
  | 'chevron'
  | 'back'
  | 'doc'
  | 'plug'
  | 'bot'
  | 'calendar'
  | 'books'
  | 'more'
  | 'mail'
  | 'lightbulb'
  | 'gift'
  | 'panel'
  | 'bell'
  | 'help'
  | 'zap'
  | 'blocks'
  | 'folder-open'
  | 'arrow-up'
  | 'close'
  | 'zoom-in'
  | 'zoom-out'
  | 'maximize'
  | 'minimize'
  | 'refresh'
  | 'stop';

type Size = 'sm' | 'md' | 'lg';

/**
 * Product chrome icon — linear stroke (edu-core WbIcon family).
 * Stroke/fill are set ON the root svg (and mirrored on symbols) because
 * CSS on <svg> does not reliably inherit into <use> shadow trees — missing
 * attrs paint as solid black fills (prod incident after #482).
 */
export default function PicoIcon({
  name,
  size = 'md',
  className,
  title,
}: {
  name: PicoIconName;
  size?: Size;
  className?: string;
  title?: string;
}) {
  const sizeClass = size === 'sm' ? 'pico-icon-sm' : size === 'lg' ? 'pico-icon-lg' : '';
  return (
    <svg
      className={cn('pico-icon', sizeClass, className)}
      viewBox="0 0 24 24"
      width={size === 'sm' ? 16 : size === 'lg' ? 23 : 20}
      height={size === 'sm' ? 16 : size === 'lg' ? 23 : 20}
      fill="none"
      stroke="currentColor"
      strokeWidth={size === 'sm' ? 2 : 1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      focusable="false"
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      <use
        href={`#pico-i-${name}`}
        xlinkHref={`#pico-i-${name}`}
        fill="none"
        stroke="currentColor"
      />
    </svg>
  );
}
