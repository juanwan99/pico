#!/usr/bin/env node
/**
 * T-UX-PLUS-ATTACH after frames on a conversation page.
 * Applies the #571 composer overflow:visible CSS on PRODUCT ChatForm so
 * Playwright can 真点 the plus menu before the yellow merge.
 */
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import crypto from 'node:crypto';
import {
  ROOT,
  loadPlaywright,
  loadEvidenceEnv,
  emailPass,
  fetchTip,
  login,
  goNewChat,
  sendPrompt,
  shot,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

const BEFORE_P1 = 'a98c1466052bdb8bc58722305b180610f650091dd5623cb93cbd685f97f495df';
const BEFORE_P3 = 'acf71aa60e0a4684e8e4c3786ef78c3df3f04d7e68cfa0edaa111888dd622569';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function tinyUploadPath() {
  const filePath = path.join(os.tmpdir(), 'pico-plus-attach-tiny.txt');
  fs.writeFileSync(filePath, 'pico attach after\n');
  return filePath;
}

async function menuPainted(page) {
  const menu = page.getByTestId('composer-plus-menu');
  if (!(await menu.count())) {
    return false;
  }
  return menu.evaluate((el) => {
    const rect = el.getBoundingClientRect();
    if (rect.width < 40 || rect.height < 40) {
      return false;
    }
    const top = document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2);
    return Boolean(top && (el === top || el.contains(top)));
  });
}

async function applyPlusAttachCss(page) {
  await page.addStyleTag({
    content: `
      .pico-wb-composer { overflow: visible !important; }
      .pico-wb-composer-row { overflow: visible !important; }
    `,
  });
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-plus-attach/after');
  fs.mkdirSync(out, { recursive: true });
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL missing');
  }
  const tip = await fetchTip(base);
  const report = {
    card: 'T-UX-PLUS-ATTACH',
    phase: 'after',
    tip,
    claim_wb: 'NO',
    note: 'conversation ChatForm + #571 overflow:visible CSS; not deployed tip',
    p1: 'N',
    p2: 'N',
    p3: 'N',
    p4: 'N',
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
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
            bytes: 18,
            file_id: `after-file-${now}`,
            temp_file_id: `after-temp-${now}`,
          }),
        });
        return;
      }
      await route.continue();
    });
    await login(page, base, email, password);
    await goNewChat(page, base);
    await sendPrompt(page, '只回一句：ping');
    await page.waitForTimeout(3500);
    await applyPlusAttachCss(page);

    const plus = page.getByTestId('composer-plus');
    await plus.waitFor({ state: 'visible', timeout: 20000 });
    await plus.click();
    const painted = await menuPainted(page);
    const p1Path = path.join(out, 'P1-chat-plus-menu-1280.png');
    const s1 = await shot(page, p1Path, { allowSmall: true });
    const p1Sha = sha256(p1Path);
    report.p1_painted = painted;
    report.p1_frame = { size: s1.size, sha: p1Sha };
    report.p1 = painted && s1.size > 20000 && p1Sha !== BEFORE_P1 ? 'Y' : 'N';

    const attach = page.getByTestId('composer-plus-attach');
    if (await attach.count()) {
      try {
        const [chooser] = await Promise.all([
          page.waitForEvent('filechooser', { timeout: 8000 }),
          attach.click(),
        ]);
        report.p2 = 'Y';
        await chooser.setFiles(tinyUploadPath());
        const chip = page.getByTestId('composer-attached-file').first();
        const named = page.getByText(/pico-plus-attach-tiny/);
        await page.waitForTimeout(1500);
        const chipOn =
          (await chip.isVisible().catch(() => false)) ||
          (await named.isVisible().catch(() => false));
        report.p3 = chipOn ? 'Y' : 'N';
      } catch (err) {
        report.p2_error = String(err?.message || err).slice(0, 240);
      }
    }
    const p3Path = path.join(out, 'P3-chip-1280.png');
    const s3 = await shot(page, p3Path, { allowSmall: true });
    const p3Sha = sha256(p3Path);
    report.p3_frame = { size: s3.size, sha: p3Sha };
    if (report.p3 === 'Y' && (s3.size <= 20000 || p3Sha === BEFORE_P3)) {
      report.p3 = 'N';
    }

    await page.setViewportSize({ width: 390, height: 844 });
    await applyPlusAttachCss(page);
    await plus.click().catch(() => {});
    const p4Painted = await menuPainted(page);
    const p4Path = path.join(out, 'P4-plus-menu-390.png');
    const s4 = await shot(page, p4Path, { allowSmall: true });
    report.p4_painted = p4Painted;
    report.p4_frame = { size: s4.size, sha: sha256(p4Path) };
    report.p4 = p4Painted ? 'Y' : 'N';

    writeJson(path.join(out, 'report.json'), report);
    console.log(JSON.stringify(report, null, 2));
    if (report.p1 !== 'Y' || report.p3 !== 'Y') {
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
