import { SUB2API_ADMIN_EXIT_URL, SUB2API_ADMIN_URL } from '../sub2apiAdmin';

describe('sub2apiAdmin', () => {
  it('uses the Pico hostname door, not a Sub2API path prefix', () => {
    expect(SUB2API_ADMIN_URL).toBe('https://pico.aivia.asia/accounts/enter-sub2api');
    expect(SUB2API_ADMIN_EXIT_URL).toBe('https://pico.aivia.asia/accounts/exit-sub2api');
    expect(SUB2API_ADMIN_URL).not.toMatch(/pico\.aivia\.asia\/sub2api/);
  });
});
