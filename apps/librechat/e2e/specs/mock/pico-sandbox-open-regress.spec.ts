import fs from 'node:fs';
import path from 'node:path';
import { expect, test, type Page } from '@playwright/test';
import { NEW_CHAT_PATH, sendMessage } from './helpers';

const FRAME_DIR = path.resolve(
  __dirname,
  '../../../../../docs/evidence/pack-sandbox-open-regress/after',
);

function ensureDir() {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
}

async function stubSandbox(page: Page, url: string, title: string, kind = 'browser') {
  const sessionId = 'sbox_e2eaaaaaaaaaaaaaaaaaaaaaa';
  await page.route('**/api/pico/v1/sandbox/sessions', async (route) => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session_id: sessionId,
          url,
          title,
          kind,
          human_copy: '请在此画面自行登录，不要在聊天里发送密码',
        }),
      });
      return;
    }
    await route.continue();
  });
  await page.route(`**/api/pico/v1/sandbox/sessions/${sessionId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        session_id: sessionId,
        url,
        title,
        kind,
        windows: [{ id: 'w1', title, kind }],
      }),
    });
  });
  await page.route(`**/api/pico/v1/sandbox/sessions/${sessionId}/screenshot`, async (route) => {
    const png = Buffer.from(
      '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000a49444154789c63000100000500010d0a2db40000000049454e44ae426082',
      'hex',
    );
    await route.fulfill({ status: 200, contentType: 'image/png', body: png });
  });
}

test.describe('T-SANDBOX-OPEN-REGRESS', () => {
  test('S1 打开 example.com mounts the right rail', async ({ page }) => {
    await stubSandbox(page, 'https://example.com/', 'Example Domain');
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '打开 https://example.com');
    await expect(page.getByTestId('result-panel')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('sandbox-web-pane')).toBeVisible({ timeout: 20000 });
    await expect(page.getByText('Example Domain').first()).toBeVisible();
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'S1-example-1280.png') });
  });

  test('S1b 打开浏览器 resolves a default Chromium page', async ({ page }) => {
    await stubSandbox(page, 'https://example.com/', 'Example Domain');
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '打开浏览器');
    await expect(page.getByTestId('result-panel')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('sandbox-web-pane')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('sandbox-empty')).toHaveCount(0);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'S1b-open-browser-1280.png') });
  });

  test('S2 打开一份 Word does not invent a classroom file', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '打开一份 Word');
    await expect(page.getByTestId('result-panel')).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('sandbox-web-pane')).toHaveCount(0);
    // No file yet — wait for generate; do not flash「没有可打开的文件」.
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'S2-word-1280.png') });
  });

  test('S3 你好 does not open the right rail', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '你好');
    await expect(page.getByText('你好').first()).toBeVisible({ timeout: 20000 });
    await expect(page.getByTestId('result-panel')).toHaveCount(0);
  });

  test('S4 390 open-website still shows sandbox', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await stubSandbox(page, 'https://example.com/', 'Example Domain');
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '打开 https://example.com');
    await expect(page.getByTestId('result-panel')).toBeVisible({ timeout: 20000 });
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'S4-390.png') });
  });
});
