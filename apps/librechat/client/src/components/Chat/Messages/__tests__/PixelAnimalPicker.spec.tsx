import React from 'react';
import { Provider, createStore } from 'jotai';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { PIXEL_ANIMAL_STORAGE_KEY, pixelAnimalIdAtom } from '~/store/pixelAnimal';
import { PixelAnimalGrid } from '../PixelAnimalPicker';

describe('PixelAnimalGrid', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('lets the user pick an animal and keeps it in localStorage', async () => {
    const user = userEvent.setup();
    const store = createStore();
    store.set(pixelAnimalIdAtom, '');

    render(
      <Provider store={store}>
        <PixelAnimalGrid userId="user-1" />
      </Provider>,
    );

    await user.click(screen.getByRole('button', { name: '狐' }));

    expect(store.get(pixelAnimalIdAtom)).toBe('fox');
    expect(JSON.parse(window.localStorage.getItem(PIXEL_ANIMAL_STORAGE_KEY) ?? '""')).toBe('fox');
  });
});
