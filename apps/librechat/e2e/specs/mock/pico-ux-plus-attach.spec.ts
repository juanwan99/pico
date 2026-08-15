import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { NEW_CHAT_PATH, sendMessage } from './helpers';

const FRAME_DIR = path.resolve(__dirname, '../../../../../docs/evidence/pack-ux-plus-attach/after');

function ensureDir() {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
}

function tinyUploadPath() {
  const filePath = path.join(os.tmpdir(), 'pico-plus-attach-tiny.txt');
  fs.writeFileSync(filePath, 'pico attach p3\n');
  return filePath;
}

/** overflow:hidden can leave a laid-out menu that Playwright still calls visible. */
async function menuIsPainted(menu: ReturnType<import('@playwright/test').Page['getByTestId']>) {
  return menu.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 40) {
      return false;
    }
    const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return Boolean(top && (el === top || el.contains(top)));
  });
}

test.describe('T-UX-PLUS-ATTACH', () => {
  test('P1 plus opens 快速 / 深度 / 上传附件', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    await plus.click();
    const menu = page.getByTestId('composer-plus-menu');
    await expect(menu).toBeVisible();
    await expect(menu.getByText('快速', { exact: true })).toBeVisible();
    await expect(menu.getByText('深度', { exact: true })).toBeVisible();
    await expect(page.getByTestId('composer-plus-attach')).toBeVisible();
    const box = await menu.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.height).toBeGreaterThan(40);
      expect(box.width).toBeGreaterThan(80);
    }
    expect(await menuIsPainted(menu)).toBeTruthy();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P1-plus-menu-1280.png') });
  });

  test('P2 上传附件 opens a real file chooser', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await page.getByTestId('composer-plus').click();
    await expect(page.getByTestId('composer-plus-attach')).toBeVisible();
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      page.getByTestId('composer-plus-attach').click(),
    ]);
    expect(chooser).toBeTruthy();
    expect(typeof chooser.setFiles).toBe('function');
  });

  test('P3 picking a file shows a chip in the composer', async ({ page }) => {
    await page.route('**/api/files**', async (route) => {
      if (route.request().method() === 'POST') {
        const now = Date.now();
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            filename: 'pico-plus-attach-tiny.txt',
            filepath: `/uploads/e2e/pico-plus-attach-tiny.txt`,
            type: 'text/plain',
            bytes: 16,
            file_id: `e2e-file-${now}`,
            temp_file_id: `e2e-temp-${now}`,
          }),
        });
        return;
      }
      await route.continue();
    });

    await page.goto(NEW_CHAT_PATH);
    await page.getByTestId('composer-plus').click();
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      page.getByTestId('composer-plus-attach').click(),
    ]);
    await chooser.setFiles(tinyUploadPath());
    const chip = page.getByTestId('composer-attached-file').first();
    await expect(chip).toBeVisible({ timeout: 10000 });
    await expect(chip).toContainText(/pico-plus-attach-tiny|tiny/i);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P3-chip-1280.png') });
  });

  test('P1-chat plus menu is visible after a turn (ChatForm, not clipped)', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '只回一句：你好');
    await expect(page.getByText('只回一句：你好')).toBeVisible({ timeout: 30000 });
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    await plus.click();
    const menu = page.getByTestId('composer-plus-menu');
    await expect(menu).toBeVisible();
    const box = await menu.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.height).toBeGreaterThan(40);
    }
    expect(await menuIsPainted(menu)).toBeTruthy();
    await expect(page.getByTestId('composer-plus-attach')).toBeVisible();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P1-chat-plus-menu-1280.png') });
  });

  test('P4 390 plus menu is visible and clickable', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    await plus.click();
    const menu = page.getByTestId('composer-plus-menu');
    await expect(menu).toBeVisible();
    const box = await menu.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.x).toBeGreaterThanOrEqual(0);
      expect(box.x + box.width).toBeLessThanOrEqual(400);
      expect(box.height).toBeGreaterThan(40);
    }
    expect(await menuIsPainted(menu)).toBeTruthy();
    await expect(page.getByTestId('composer-plus-attach')).toBeVisible();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P4-plus-menu-390.png') });
  });
});
