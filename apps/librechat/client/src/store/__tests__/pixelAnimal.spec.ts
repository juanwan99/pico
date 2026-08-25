import { PIXEL_ANIMALS, pixelAnimalById } from '../pixelAnimal';

describe('pixelAnimals catalog', () => {
  it('ships a fixed CC0 set with public static paths', () => {
    expect(PIXEL_ANIMALS.length).toBeGreaterThanOrEqual(8);
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
});
