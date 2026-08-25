import { useEffect } from 'react';
import { useAtom } from 'jotai';
import {
  PIXEL_ANIMALS,
  defaultAnimalIdForUser,
  pixelAnimalById,
  pixelAnimalIdAtom,
  resolvePixelAnimalId,
} from '~/store/pixelAnimal';
import { cn } from '~/utils';

function useEnsuredAnimalId(userId: string) {
  const [storedId, setStoredId] = useAtom(pixelAnimalIdAtom);

  useEffect(() => {
    if (!pixelAnimalById(storedId)) {
      setStoredId(defaultAnimalIdForUser(userId));
    }
  }, [storedId, userId, setStoredId]);

  return resolvePixelAnimalId(userId, storedId);
}

/** Static zoo-js animal grid. Shown in Settings → Account only. */
export function PixelAnimalGrid({
  userId = '',
  onPicked,
}: {
  userId?: string;
  onPicked?: () => void;
}) {
  const [, setSelectedId] = useAtom(pixelAnimalIdAtom);
  const activeId = useEnsuredAnimalId(userId);

  return (
    <div className="grid grid-cols-5 gap-2">
      {PIXEL_ANIMALS.map((animal) => (
        <button
          key={animal.id}
          type="button"
          aria-label={animal.label}
          aria-pressed={activeId === animal.id}
          className={cn(
            'flex items-center justify-center rounded-lg p-1 hover:bg-surface-hover',
            activeId === animal.id && 'ring-2 ring-border-xheavy',
          )}
          onClick={() => {
            setSelectedId(animal.id);
            onPicked?.();
          }}
        >
          <img src={animal.src} alt={animal.label} className="h-9 w-9 rounded-full" width={36} height={36} />
        </button>
      ))}
    </div>
  );
}

export function PixelAnimalFace({
  size,
  userId = '',
  className,
}: {
  size: number;
  userId?: string;
  className?: string;
}) {
  const id = useEnsuredAnimalId(userId);
  const selected = pixelAnimalById(id);
  if (!selected) {
    return null;
  }
  return (
    <img
      src={selected.src}
      alt={selected.label}
      width={size}
      height={size}
      className={cn('rounded-full object-cover', className)}
    />
  );
}
