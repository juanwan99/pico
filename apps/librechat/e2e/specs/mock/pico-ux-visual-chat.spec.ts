import fs from 'node:fs';
import path from 'node:path';
import { expect, test } from '@playwright/test';
import { NEW_CHAT_PATH, sendMessage } from './helpers';

const FRAME_DIR = path.resolve(__dirname, '../../../../../docs/evidence/pack-ux-visual-chat/after');

function ensureDir() {
  fs.mkdirSync(FRAME_DIR, { recursive: true });
}

test.describe('T-UX-VISUAL-CHAT', () => {
  test('V1 idle middle: one title, one-row composer, no header pico-fast / second +', async ({
    page,
  }) => {
    await page.goto(NEW_CHAT_PATH);
    await expect(page.getByRole('heading', { name: 'Pico，我帮你' })).toBeVisible();
    await expect(page.getByText('日常办公')).toHaveCount(0);
    await expect(page.getByText('今天帮你做些什么？')).toHaveCount(0);
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    await expect(input).toBeVisible();
    expect(await input.getAttribute('placeholder')).toBe('发消息');
    const row = page.getByTestId('composer-one-row');
    await expect(row).toBeVisible();
    const box = await row.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.height).toBeLessThan(88);
    }
    await expect(page.getByTestId('model-selector-button')).toHaveCount(0);
    await expect(page.getByTestId('add-multi-convo-button')).toHaveCount(0);
    await expect(page.getByTestId('bookmark-menu')).toHaveCount(0);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'V1-empty-middle-1280.png') });
  });

  test('V2 plus is 快速 / 深度 / 上传附件 only', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await page.getByTestId('composer-plus').click();
    const menu = page.getByTestId('composer-plus-menu');
    await expect(menu).toBeVisible();
    await expect(menu.getByText('快速', { exact: true })).toBeVisible();
    await expect(menu.getByText('深度', { exact: true })).toBeVisible();
    await expect(page.getByTestId('composer-plus-attach')).toBeVisible();
    await expect(menu.getByText(/工作空间/)).toHaveCount(0);
    await expect(menu.getByText(/默认权限/)).toHaveCount(0);
    await expect(menu.getByText(/Token|Badge|工作空间|默认权限/)).toHaveCount(0);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'V2-plus-open-1280.png') });
  });

  test('V3 one bubble: no identity dashboard, no auto right rail', async ({ page }) => {
    await page.goto(NEW_CHAT_PATH);
    await sendMessage(page, '只回一句：你好');
    await expect(page.getByText('只回一句：你好')).toBeVisible();
    await expect(page.getByTestId('model-selector-button')).toHaveCount(0);
    await expect(page.getByTestId('add-multi-convo-button')).toHaveCount(0);
    await expect(page.getByRole('heading', { name: 'OpenAI' })).toHaveCount(0);
    await expect(page.getByTestId('result-panel')).toHaveCount(0);
    await expect(page.getByText('打开我的文件', { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('pico-search-sources')).toHaveCount(0);
    const input = page.locator('#pico-wb-home-input, [data-testid="text-input"]').first();
    expect(await input.getAttribute('placeholder')).not.toMatch(/今天帮你做些什么/);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'V3-one-bubble-1280.png') });
  });

  test('V5 390 middle stays usable', async ({ page }) => {
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
    await expect(page.getByTestId('model-selector-button')).toHaveCount(0);
    ensureDir();
    await page.screenshot({ path: path.join(FRAME_DIR, 'V5-390-middle.png') });
  });
});
