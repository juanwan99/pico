/**
 * Sub2API account-admin door on the public Pico hostname.
 * Nginx cookie-switches this origin to loopback Sub2API (SPA cannot use a path prefix).
 * Pico does not CRUD accounts and does not call Sub2API for inference.
 */
export const SUB2API_ADMIN_URL = 'https://pico.aivia.asia/accounts/enter-sub2api';
export const SUB2API_ADMIN_EXIT_URL = 'https://pico.aivia.asia/accounts/exit-sub2api';
