import { atom } from 'recoil';
import Cookies from 'js-cookie';
import { atomWithLocalStorage } from './utils';

/** Pico product default: Simplified Chinese (not browser English). */
export const PICO_DEFAULT_LOCALE = 'zh-Hans';

const readStoredLang = () => {
  if (typeof localStorage === 'undefined') {
    return undefined;
  }

  const storedLang = localStorage.getItem('lang');
  if (!storedLang) {
    return undefined;
  }

  try {
    const parsedLang = JSON.parse(storedLang);
    return typeof parsedLang === 'string' ? parsedLang : storedLang;
  } catch {
    return storedLang;
  }
};

/**
 * Prefer explicit user choice; otherwise Pico ships in 简体中文.
 * Sandbox / Playwright often leave lang=en — treat bare English as unset for product.
 */
const defaultLang = () => {
  const stored = Cookies.get('lang') || readStoredLang();
  if (!stored) {
    return PICO_DEFAULT_LOCALE;
  }
  const normalized = String(stored).replace(/_/g, '-').toLowerCase();
  if (normalized === 'en' || normalized === 'en-us' || normalized === 'en-gb') {
    return PICO_DEFAULT_LOCALE;
  }
  return stored;
};

const lang = atomWithLocalStorage('lang', defaultLang());
const languageLoading = atom<boolean>({
  key: 'languageLoading',
  default: false,
});

export default { lang, languageLoading };
