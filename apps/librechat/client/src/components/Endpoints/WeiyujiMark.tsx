import { cn } from '~/utils';

const WEIYUJI_MARK_SRC = '/assets/weiyuji-mark.svg';

/**
 * Existing 微与积 mark (copied from edu-core logo-mark.svg into pico public assets).
 * Not a drawn avatar; static SVG only.
 */
export default function WeiyujiMark({
  size = 28.8,
  className,
}: {
  size?: number;
  className?: string;
}) {
  return (
    <img
      src={WEIYUJI_MARK_SRC}
      alt="微与积"
      width={size}
      height={size}
      className={cn('h-full w-full object-contain', className)}
    />
  );
}

export { WEIYUJI_MARK_SRC };
