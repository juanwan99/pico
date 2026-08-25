import type { ReactNode } from 'react';
import { useAtom } from 'jotai';
import * as Popover from '@radix-ui/react-popover';
import { PIXEL_ANIMALS, pixelAnimalIdAtom } from '~/store/pixelAnimal';
import { cn } from '~/utils';

/**
 * Click-own-avatar picker. Uses the CC0 Tiny Creatures tile set (static PNGs).
 * Does not draw avatars.
 */
export default function PixelAnimalPicker({ children }: { children: ReactNode }) {
  const [selectedId, setSelectedId] = useAtom(pixelAnimalIdAtom);

  return (
    <Popover.Root>
      <Popover.Trigger asChild>
        <button
          type="button"
          aria-label="更换像素动物头像"
          className="flex items-center justify-center rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-border-xheavy"
        >
          {children}
        </button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="right"
          align="start"
          sideOffset={8}
          className="z-50 w-56 rounded-xl border border-border-medium bg-surface-primary p-3 shadow-lg"
        >
          <p className="mb-2 text-sm font-medium text-text-primary">选一只像素动物</p>
          <div className="grid grid-cols-4 gap-2">
            {PIXEL_ANIMALS.map((animal) => (
              <button
                key={animal.id}
                type="button"
                aria-label={animal.label}
                aria-pressed={selectedId === animal.id}
                className={cn(
                  'flex items-center justify-center rounded-lg p-1 hover:bg-surface-hover',
                  selectedId === animal.id && 'ring-2 ring-border-xheavy',
                )}
                onClick={() => setSelectedId(animal.id)}
              >
                <img
                  src={animal.src}
                  alt={animal.label}
                  className="pico-pixel-animal h-8 w-8"
                  width={32}
                  height={32}
                />
              </button>
            ))}
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
