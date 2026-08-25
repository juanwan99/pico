import { createStorageAtom } from './jotai-utils';

export const PIXEL_ANIMAL_STORAGE_KEY = 'pico.pixelAnimalId';

export const PIXEL_ANIMALS = [
  { id: 'cat', src: '/assets/pixel-animals/cat.png', label: '猫' },
  { id: 'kitten', src: '/assets/pixel-animals/kitten.png', label: '小猫' },
  { id: 'dog', src: '/assets/pixel-animals/dog.png', label: '狗' },
  { id: 'rabbit', src: '/assets/pixel-animals/rabbit.png', label: '兔' },
  { id: 'fox', src: '/assets/pixel-animals/fox.png', label: '狐' },
  { id: 'panda', src: '/assets/pixel-animals/panda.png', label: '熊猫' },
  { id: 'penguin', src: '/assets/pixel-animals/penguin.png', label: '企鹅' },
  { id: 'hamster', src: '/assets/pixel-animals/hamster.png', label: '仓鼠' },
  { id: 'koala', src: '/assets/pixel-animals/koala.png', label: '考拉' },
  { id: 'owl', src: '/assets/pixel-animals/owl.png', label: '猫头鹰' },
  { id: 'frog', src: '/assets/pixel-animals/frog.png', label: '蛙' },
  { id: 'chick', src: '/assets/pixel-animals/chick.png', label: '小鸡' },
  { id: 'duck', src: '/assets/pixel-animals/duck.png', label: '鸭' },
  { id: 'pig', src: '/assets/pixel-animals/pig.png', label: '猪' },
  { id: 'sheep', src: '/assets/pixel-animals/sheep.png', label: '羊' },
  { id: 'bear', src: '/assets/pixel-animals/bear.png', label: '熊' },
  { id: 'lion', src: '/assets/pixel-animals/lion.png', label: '狮' },
  { id: 'tiger', src: '/assets/pixel-animals/tiger.png', label: '虎' },
  { id: 'elephant', src: '/assets/pixel-animals/elephant.png', label: '象' },
  { id: 'giraffe', src: '/assets/pixel-animals/giraffe.png', label: '长颈鹿' },
  { id: 'dolphin', src: '/assets/pixel-animals/dolphin.png', label: '海豚' },
  { id: 'otter', src: '/assets/pixel-animals/otter.png', label: '水獭' },
  { id: 'raccoon', src: '/assets/pixel-animals/raccoon.png', label: '浣熊' },
  { id: 'sloth', src: '/assets/pixel-animals/sloth.png', label: '树懒' },
  { id: 'hedgehog', src: '/assets/pixel-animals/hedgehog.png', label: '刺猬' },
  { id: 'squirrel', src: '/assets/pixel-animals/squirrel.png', label: '松鼠' },
  { id: 'capybara', src: '/assets/pixel-animals/capybara.png', label: '水豚' },
  { id: 'polar', src: '/assets/pixel-animals/polar.png', label: '北极熊' },
  { id: 'wolf', src: '/assets/pixel-animals/wolf.png', label: '狼' },
  { id: 'bird', src: '/assets/pixel-animals/bird.png', label: '鸟' },
] as const;

export type PixelAnimalId = (typeof PIXEL_ANIMALS)[number]['id'];

export function pixelAnimalById(id: string | null | undefined) {
  if (!id) {
    return null;
  }
  return PIXEL_ANIMALS.find((animal) => animal.id === id) ?? null;
}

/** Stable per-user default so each account starts on a different animal. */
export function defaultAnimalIdForUser(userId: string): PixelAnimalId {
  const seed = userId || 'pico-guest';
  let hash = 2166136261;
  for (let i = 0; i < seed.length; i += 1) {
    hash ^= seed.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return PIXEL_ANIMALS[(hash >>> 0) % PIXEL_ANIMALS.length].id;
}

export function resolvePixelAnimalId(
  userId: string,
  storedId: string | null | undefined,
): PixelAnimalId {
  if (pixelAnimalById(storedId)) {
    return storedId as PixelAnimalId;
  }
  return defaultAnimalIdForUser(userId);
}

/** Persists across refresh. Empty string = use per-user default until the user picks. */
export const pixelAnimalIdAtom = createStorageAtom<string>(PIXEL_ANIMAL_STORAGE_KEY, '');
