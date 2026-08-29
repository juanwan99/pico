import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { NEW_CHAT_PATH } from './helpers';

const FRAME_DIR = path.resolve(__dirname, '../../../../../docs/evidence/pack-ux-composer-type-icon');

/**
 * T-UX-COMPOSER-TYPE-ICON · C1–C5 against the mock LibreChat stack.
 */
function verticalOverlap(a: { y: number; height: number }, b: { y: number; height: number }) {
  const aMid = a.y + a.height / 2;
  return aMid >= b.y - 4 && aMid <= b.y + b.height + 4;
}

test.describe('T-UX-COMPOSER-TYPE-ICON', () => {
  test('C1 idle composer is one row: plus · input · send', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const row = page.getByTestId('composer-one-row');
    const plus = page.getByTestId('composer-plus');
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    const send = page.getByTestId('send-button');
    await expect(row).toBeVisible();
    await expect(plus).toBeVisible();
    await expect(input).toBeVisible();
    await expect(send).toBeVisible();
    await expect(page.getByTestId('composer-plus-menu')).toHaveCount(0);

    const [rowBox, plusBox, inputBox, sendBox] = await Promise.all([
      row.boundingBox(),
      plus.boundingBox(),
      input.boundingBox(),
      send.boundingBox(),
    ]);
    expect(rowBox).not.toBeNull();
    expect(plusBox).not.toBeNull();
    expect(inputBox).not.toBeNull();
    expect(sendBox).not.toBeNull();
    if (rowBox && plusBox && inputBox && sendBox) {
      expect(verticalOverlap(plusBox, rowBox)).toBeTruthy();
      expect(verticalOverlap(inputBox, rowBox)).toBeTruthy();
      expect(verticalOverlap(sendBox, rowBox)).toBeTruthy();
      expect(Math.abs(plusBox.y - sendBox.y)).toBeLessThan(16);
      expect(rowBox.height).toBeLessThan(88);
    }
    const plusText = ((await plus.textContent()) || '').trim();
    expect(plusText).not.toBe('+');
    fs.mkdirSync(FRAME_DIR, { recursive: true });
    await page.screenshot({ path: path.join(FRAME_DIR, 'c1-one-row-mock.png') });
  });

  test('C2 plus opens the file chooser; 快速/深度 is a visible switch', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await expect(page.getByTestId('composer-mode-switch')).toBeVisible();
    await expect(page.getByTestId('composer-plus-menu')).toHaveCount(0);
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      page.getByTestId('composer-plus').click(),
    ]);
    expect(chooser).toBeTruthy();
    fs.mkdirSync(FRAME_DIR, { recursive: true });
    await page.screenshot({ path: path.join(FRAME_DIR, 'c2-plus-closed-mock.png') });
  });

  test('C3 body font uses CJK stack at 15px', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    await expect(input).toBeVisible();
    const style = await input.evaluate((el) => {
      const computed = getComputedStyle(el);
      return { fontSize: computed.fontSize, fontFamily: computed.fontFamily };
    });
    expect(parseFloat(style.fontSize)).toBe(15);
    expect(style.fontFamily.toLowerCase()).not.toMatch(/^\s*inter\b/);
    expect(style.fontFamily).toMatch(/PingFang|Hiragino|Source Han|Noto Sans SC|Microsoft YaHei|Heiti/i);
  });

  test('C4 sidebar+composer have no lucide and only one 新对话', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const lucide = page.locator(
      '.pico-wb-sidebar svg.lucide, .pico-wb-composer svg.lucide, .pico-wb-sidebar [class*="lucide-"], .pico-wb-composer [class*="lucide-"]',
    );
    expect(await lucide.count()).toBe(0);
    const newChats = page.getByRole('button', { name: '新对话' });
    expect(await newChats.count()).toBeLessThanOrEqual(1);
    await expect(page.getByTestId('nav-search-input')).toHaveCount(0);
  });

  test('C5 390 composer does not overflow', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(NEW_CHAT_PATH);
    const row = page.getByTestId('composer-one-row');
    await expect(row).toBeVisible();
    const box = await row.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.x + box.width).toBeLessThanOrEqual(400);
      expect(box.height).toBeLessThan(88);
    }
  });
});
