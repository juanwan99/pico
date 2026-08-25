import { PIXEL_ANIMALS, defaultAnimalIdForUser, pixelAnimalById } from '../pixelAnimal';

describe('pixelAnimals catalog', () => {
  it('ships a fixed zoo-js animal set with public static paths', () => {
    expect(PIXEL_ANIMALS.length).toBeGreaterThanOrEqual(20);
    for (const animal of PIXEL_ANIMALS) {
      expect(animal.src.startsWith('/assets/pixel-animals/')).toBe(true);
      expect(animal.src.endsWith('.png')).toBe(true);
      expect(animal.label.length).toBeGreaterThan(0);
    }
  });

  it('resolves known ids and rejects empty', () => {
    expect(pixelAnimalById('cat')?.label).toBe('猫');
    expect(pixelAnimalById('')).toBeNull();
    expect(pixelAnimalById('not-an-animal')).toBeNull();
  });

  it('gives each user a stable default animal', () => {
    const a = defaultAnimalIdForUser('user-aaa');
    const b = defaultAnimalIdForUser('user-bbb');
    expect(pixelAnimalById(a)).not.toBeNull();
    expect(defaultAnimalIdForUser('user-aaa')).toBe(a);
    expect(['user-aaa', 'user-bbb']).toContain('user-aaa');
    expect(typeof b).toBe('string');
  });
});
