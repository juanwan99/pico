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

test.describe('T-UX-PLUS-ATTACH', () => {
  test('P1 plus opens the file chooser; 快速/深度 is a switch', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    await expect(page.getByTestId('composer-mode-switch')).toBeVisible();
    await expect(page.getByTestId('composer-plus-mode-pico-fast')).toBeVisible();
    await expect(page.getByTestId('composer-plus-mode-pico-deep')).toBeVisible();
    await expect(page.getByTestId('composer-plus-menu')).toHaveCount(0);
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      plus.click(),
    ]);
    expect(chooser).toBeTruthy();
    expect(typeof chooser.setFiles).toBe('function');
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P1-plus-menu-1280.png') });
  });

  test('P2 + opens a real file chooser', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      page.getByTestId('composer-plus').click(),
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
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      page.getByTestId('composer-plus').click(),
    ]);
    await chooser.setFiles(tinyUploadPath());
    const chip = page.getByTestId('composer-attached-file').first();
    await expect(chip).toBeVisible({ timeout: 10000 });
    await expect(chip).toContainText(/pico-plus-attach-tiny|tiny/i);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P3-chip-1280.png') });
  });

  test('P1-chat plus still opens the file chooser after a turn', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '只回一句：你好');
    await expect(page.getByText('只回一句：你好')).toBeVisible({ timeout: 30000 });
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    await expect(page.getByTestId('composer-mode-switch')).toBeVisible();
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      plus.click(),
    ]);
    expect(chooser).toBeTruthy();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P1-chat-plus-menu-1280.png') });
  });

  test('P4 390 plus opens the file chooser', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto(NEW_CHAT_PATH);
    const plus = page.getByTestId('composer-plus');
    await expect(plus).toBeVisible();
    const [chooser] = await Promise.all([
      page.waitForEvent('filechooser', { timeout: 8000 }),
      plus.click(),
    ]);
    expect(chooser).toBeTruthy();
    await expect(page.getByTestId('composer-mode-switch')).toBeVisible();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'P4-plus-menu-390.png') });
  });
});
