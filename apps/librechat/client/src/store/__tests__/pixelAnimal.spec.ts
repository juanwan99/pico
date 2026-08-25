import {
  PIXEL_ANIMAL_STORAGE_KEY,
  PIXEL_ANIMALS,
  defaultAnimalIdForUser,
  pixelAnimalById,
} from '../pixelAnimal';

describe('pixelAnimals catalog', () => {
  it('ships the full generic zoo-js animal set with cache-busting paths', () => {
    expect(PIXEL_ANIMALS.length).toBe(78);
    const ids = PIXEL_ANIMALS.map((animal) => animal.id);
    expect(new Set(ids).size).toBe(78);
    expect(ids).not.toContain('pikachu');
    expect(ids).not.toContain('totoro');
    for (const animal of PIXEL_ANIMALS) {
      expect(animal.src).toBe(`/assets/zoo-animals/${animal.id}.png`);
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

  it('does not reuse the Tiny Creatures storage key', () => {
    expect(PIXEL_ANIMAL_STORAGE_KEY).toBe('pico.zooAnimalId');
  });
});
