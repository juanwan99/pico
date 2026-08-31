import type { ReactNode } from 'react';

/** Label column + stretching control. Same left/right edge as the composer. */
export default function ComposerChromeRow({
  label,
  children,
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <div className="pico-composer-chrome-row mb-2 w-full">
      <span className="pico-type-body pico-composer-chrome-label text-[color:var(--pico-ink-2)]">
        {label}
      </span>
      <div className="pico-composer-chrome-control min-w-0 w-full">{children}</div>
    </div>
  );
}
