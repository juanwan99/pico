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
  | 'folder-open';

type Size = 'sm' | 'md' | 'lg';

/**
 * Product chrome icon — linear stroke, edu-core WbIcon family.
 * Requires <PicoIconSprite /> mounted once under .pico-app.
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
      aria-hidden={title ? undefined : true}
      focusable="false"
      role={title ? 'img' : undefined}
    >
      {title ? <title>{title}</title> : null}
      <use href={`#pico-i-${name}`} />
    </svg>
  );
}
