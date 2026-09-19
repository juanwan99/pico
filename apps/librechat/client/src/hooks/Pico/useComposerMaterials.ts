import { useCallback, useState } from 'react';

const KEY = 'pico:composerMaterials';

export function useComposerMaterials() {
  const [open, setOpen] = useState(() => {
    try {
      return sessionStorage.getItem(KEY) === '1';
    } catch {
      return false;
    }
  });
  const toggle = useCallback(() => {
    setOpen((prev) => {
      const next = !prev;
      try {
        sessionStorage.setItem(KEY, next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  return { open, toggle };
}
