import { createStorageAtom } from './jotai-utils';

export const PIXEL_ANIMAL_STORAGE_KEY = 'pico.pixelAnimalId';

export const PIXEL_ANIMALS = [
  { id: 'cat', src: '/assets/pixel-animals/cat.png', label: '猫' },
  { id: 'dog', src: '/assets/pixel-animals/dog.png', label: '狗' },
  { id: 'rabbit', src: '/assets/pixel-animals/rabbit.png', label: '兔' },
  { id: 'fox', src: '/assets/pixel-animals/fox.png', label: '狐' },
  { id: 'owl', src: '/assets/pixel-animals/owl.png', label: '猫头鹰' },
  { id: 'frog', src: '/assets/pixel-animals/frog.png', label: '蛙' },
  { id: 'chicken', src: '/assets/pixel-animals/chicken.png', label: '鸡' },
  { id: 'sheep', src: '/assets/pixel-animals/sheep.png', label: '羊' },
  { id: 'polar', src: '/assets/pixel-animals/polar.png', label: '北极熊' },
  { id: 'giraffe', src: '/assets/pixel-animals/giraffe.png', label: '长颈鹿' },
  { id: 'raccoon', src: '/assets/pixel-animals/raccoon.png', label: '浣熊' },
  { id: 'turtle', src: '/assets/pixel-animals/turtle.png', label: '龟' },
] as const;

export type PixelAnimalId = (typeof PIXEL_ANIMALS)[number]['id'];

export function pixelAnimalById(id: string | null | undefined) {
  if (!id) {
    return null;
  }
  return PIXEL_ANIMALS.find((animal) => animal.id === id) ?? null;
}

/** Persists across refresh. Empty string = not yet picked (keep default user icon). */
export const pixelAnimalIdAtom = createStorageAtom<string>(PIXEL_ANIMAL_STORAGE_KEY, '');
