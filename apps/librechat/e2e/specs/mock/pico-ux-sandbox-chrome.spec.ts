import { expect, test } from '@playwright/test';
import { NEW_CHAT_PATH } from './helpers';

/**
 * T-UX-SANDBOX-CHROME · U1–U4 against the mock LibreChat stack.
 * Jest covers component branches; this file is the human Playwright path.
 */
test.describe('T-UX-SANDBOX-CHROME', () => {
  test('U1 idle composer is one input + plus, no skill second layer', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    const body = await page.locator('body').innerText();
    expect(body).not.toMatch(/调用技能与指令/);
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    await expect(input).toBeVisible();
    const placeholder = await input.getAttribute('placeholder');
    expect(placeholder || '').not.toMatch(/调用技能/);
  });

  test('U4 390 composer does not stretch and right rail can close', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    const box = await plus.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.x + box.width).toBeLessThanOrEqual(400);
    }
    const close = page.getByTestId('result-panel-close');
    if (await close.count()) {
      await close.click();
      await expect(page.getByTestId('result-panel-toggle')).toBeVisible();
    }
  });
});
