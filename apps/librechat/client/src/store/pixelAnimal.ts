import { createStorageAtom } from './jotai-utils';

/** New key so Tiny Creatures picks in pico.pixelAnimalId are dropped. */
export const PIXEL_ANIMAL_STORAGE_KEY = 'pico.zooAnimalId';

export const PIXEL_ANIMALS = [
  { id: 'alpaca', src: '/assets/zoo-animals/alpaca.png', label: '羊驼' },
  { id: 'bat', src: '/assets/zoo-animals/bat.png', label: '蝙蝠' },
  { id: 'bear', src: '/assets/zoo-animals/bear.png', label: '熊' },
  { id: 'beetle', src: '/assets/zoo-animals/beetle.png', label: '甲壳虫' },
  { id: 'bird', src: '/assets/zoo-animals/bird.png', label: '小鸟' },
  { id: 'butterfly', src: '/assets/zoo-animals/butterfly.png', label: '蝴蝶' },
  { id: 'camel', src: '/assets/zoo-animals/camel.png', label: '骆驼' },
  { id: 'canary', src: '/assets/zoo-animals/canary.png', label: '金丝雀' },
  { id: 'capybara', src: '/assets/zoo-animals/capybara.png', label: '水豚' },
  { id: 'cat', src: '/assets/zoo-animals/cat.png', label: '猫' },
  { id: 'cattle', src: '/assets/zoo-animals/cattle.png', label: '牛' },
  { id: 'chameleon', src: '/assets/zoo-animals/chameleon.png', label: '变色龙' },
  { id: 'chick', src: '/assets/zoo-animals/chick.png', label: '小鸡' },
  { id: 'cicada', src: '/assets/zoo-animals/cicada.png', label: '蝉' },
  { id: 'clownfish', src: '/assets/zoo-animals/clownfish.png', label: '小丑鱼' },
  { id: 'crab', src: '/assets/zoo-animals/crab.png', label: '螃蟹' },
  { id: 'deer', src: '/assets/zoo-animals/deer.png', label: '鹿' },
  { id: 'dinosaur', src: '/assets/zoo-animals/dinosaur.png', label: '恐龙' },
  { id: 'dog', src: '/assets/zoo-animals/dog.png', label: '狗' },
  { id: 'dolphin', src: '/assets/zoo-animals/dolphin.png', label: '海豚' },
  { id: 'dragon', src: '/assets/zoo-animals/dragon.png', label: '龙' },
  { id: 'duck', src: '/assets/zoo-animals/duck.png', label: '鸭子' },
  { id: 'ducky', src: '/assets/zoo-animals/ducky.png', label: '小鸭' },
  { id: 'elephant', src: '/assets/zoo-animals/elephant.png', label: '大象' },
  { id: 'flamingo', src: '/assets/zoo-animals/flamingo.png', label: '火烈鸟' },
  { id: 'fox', src: '/assets/zoo-animals/fox.png', label: '狐狸' },
  { id: 'frog', src: '/assets/zoo-animals/frog.png', label: '青蛙' },
  { id: 'giraffe', src: '/assets/zoo-animals/giraffe.png', label: '长颈鹿' },
  { id: 'goblin', src: '/assets/zoo-animals/goblin.png', label: '哥布林' },
  { id: 'goldfish', src: '/assets/zoo-animals/goldfish.png', label: '金鱼' },
  { id: 'gull', src: '/assets/zoo-animals/gull.png', label: '海鸥' },
  { id: 'hamster', src: '/assets/zoo-animals/hamster.png', label: '仓鼠' },
  { id: 'hedgehog', src: '/assets/zoo-animals/hedgehog.png', label: '刺猬' },
  { id: 'hippo', src: '/assets/zoo-animals/hippo.png', label: '河马' },
  { id: 'honeybee', src: '/assets/zoo-animals/honeybee.png', label: '小蜜蜂' },
  { id: 'horse', src: '/assets/zoo-animals/horse.png', label: '马' },
  { id: 'jellyfish', src: '/assets/zoo-animals/jellyfish.png', label: '海蜇' },
  { id: 'kangaroo', src: '/assets/zoo-animals/kangaroo.png', label: '袋鼠' },
  { id: 'kitten', src: '/assets/zoo-animals/kitten.png', label: '小猫' },
  { id: 'koala', src: '/assets/zoo-animals/koala.png', label: '考拉' },
  { id: 'lark', src: '/assets/zoo-animals/lark.png', label: '云雀' },
  { id: 'lion', src: '/assets/zoo-animals/lion.png', label: '狮子' },
  { id: 'monkey', src: '/assets/zoo-animals/monkey.png', label: '猴子' },
  { id: 'mouse', src: '/assets/zoo-animals/mouse.png', label: '老鼠' },
  { id: 'octopus', src: '/assets/zoo-animals/octopus.png', label: '章鱼' },
  { id: 'orangutan', src: '/assets/zoo-animals/orangutan.png', label: '猩猩' },
  { id: 'otter', src: '/assets/zoo-animals/otter.png', label: '水獭' },
  { id: 'owl', src: '/assets/zoo-animals/owl.png', label: '猫头鹰' },
  { id: 'panda', src: '/assets/zoo-animals/panda.png', label: '熊猫' },
  { id: 'parrot', src: '/assets/zoo-animals/parrot.png', label: '鹦鹉' },
  { id: 'peacock', src: '/assets/zoo-animals/peacock.png', label: '孔雀' },
  { id: 'pelican', src: '/assets/zoo-animals/pelican.png', label: '鹈鹕' },
  { id: 'penguin', src: '/assets/zoo-animals/penguin.png', label: '企鹅' },
  { id: 'pig', src: '/assets/zoo-animals/pig.png', label: '猪' },
  { id: 'pigeon', src: '/assets/zoo-animals/pigeon.png', label: '鸽子' },
  { id: 'polar', src: '/assets/zoo-animals/polar.png', label: '北极熊' },
  { id: 'rabbit', src: '/assets/zoo-animals/rabbit.png', label: '兔子' },
  { id: 'raccoon', src: '/assets/zoo-animals/raccoon.png', label: '浣熊' },
  { id: 'reindeer', src: '/assets/zoo-animals/reindeer.png', label: '驯鹿' },
  { id: 'rhinoceros', src: '/assets/zoo-animals/rhinoceros.png', label: '犀牛' },
  { id: 'seal', src: '/assets/zoo-animals/seal.png', label: '海豹' },
  { id: 'shark', src: '/assets/zoo-animals/shark.png', label: '鲨鱼' },
  { id: 'sheep', src: '/assets/zoo-animals/sheep.png', label: '羊' },
  { id: 'shrimp', src: '/assets/zoo-animals/shrimp.png', label: '虾' },
  { id: 'sloth', src: '/assets/zoo-animals/sloth.png', label: '树懒' },
  { id: 'snail', src: '/assets/zoo-animals/snail.png', label: '蜗牛' },
  { id: 'snake', src: '/assets/zoo-animals/snake.png', label: '蛇' },
  { id: 'spider', src: '/assets/zoo-animals/spider.png', label: '蜘蛛' },
  { id: 'squirrel', src: '/assets/zoo-animals/squirrel.png', label: '松鼠' },
  { id: 'starfish', src: '/assets/zoo-animals/starfish.png', label: '海星' },
  { id: 'swallow', src: '/assets/zoo-animals/swallow.png', label: '燕子' },
  { id: 'swan', src: '/assets/zoo-animals/swan.png', label: '天鹅' },
  { id: 'tiger', src: '/assets/zoo-animals/tiger.png', label: '老虎' },
  { id: 'tortoise', src: '/assets/zoo-animals/tortoise.png', label: '乌龟' },
  { id: 'unicorn', src: '/assets/zoo-animals/unicorn.png', label: '独角兽' },
  { id: 'whale', src: '/assets/zoo-animals/whale.png', label: '鲸鱼' },
  { id: 'wolf', src: '/assets/zoo-animals/wolf.png', label: '狼' },
  { id: 'zebra', src: '/assets/zoo-animals/zebra.png', label: '斑马' },
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
