#!/usr/bin/env node
/**
 * T-UX-PLUS-ATTACH public frames: click + (P1) and attach chip (P3).
 * PHASE=before|after. Not a feature change.
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
  shot,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

const PHASE = process.env.PHASE || 'before';
const EXPECT = process.env.PICO_EXPECT_TIP || '';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

function tinyUploadPath() {
  const filePath = path.join(os.tmpdir(), 'pico-plus-attach-tiny.txt');
  fs.writeFileSync(filePath, 'pico attach public\n');
  return filePath;
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-plus-attach', PHASE);
  fs.mkdirSync(out, { recursive: true });
  const { email, password } = emailPass();
  if (!email || !password) {
    throw new Error('DEMO_EMAIL missing');
  }
  const tip = await fetchTip(base);
  if (EXPECT && tip.git_sha !== EXPECT) {
    throw new Error(`tip ${tip.git_sha} != ${EXPECT}`);
  }
  const report = {
    card: 'T-UX-PLUS-ATTACH',
    phase: PHASE,
    tip,
    p1: 'N',
    p2: 'N',
    p3: 'N',
    p4: 'N',
    claim_wb: 'NO',
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
    await login(page, base, email, password);
    await goNewChat(page, base);
    const plus = page.getByTestId('composer-plus');
    await plus.waitFor({ state: 'visible', timeout: 20000 });
    await plus.click();
    const menu = page.getByTestId('composer-plus-menu');
    const menuCount = await menu.count();
    const menuBox = menuCount ? await menu.boundingBox() : null;
    const p1Path = path.join(out, 'P1-plus-menu-1280.png');
    const s1 = await shot(page, p1Path, { allowSmall: true });
    report.p1_menu_count = menuCount;
    report.p1_menu_box = menuBox;
    report.p1_frame = { size: s1.size, sha: sha256(p1Path) };
    let painted = false;
    if (menuCount) {
      painted = await menu.evaluate((el) => {
        const rect = el.getBoundingClientRect();
        const top = document.elementFromPoint(
          rect.left + rect.width / 2,
          rect.top + rect.height / 2,
        );
        return Boolean(top && (el === top || el.contains(top)));
      });
    }
    report.p1_painted = painted;
    report.p1 = menuCount && menuBox && menuBox.height > 20 && painted ? 'Y' : 'N';

    let chooserOpened = false;
    if (menuCount) {
      const attach = page.getByTestId('composer-plus-attach');
      if (await attach.count()) {
        try {
          const [chooser] = await Promise.all([
            page.waitForEvent('filechooser', { timeout: 6000 }),
            attach.click(),
          ]);
          chooserOpened = Boolean(chooser);
          report.p2 = chooserOpened ? 'Y' : 'N';
          if (chooserOpened) {
            await chooser.setFiles(tinyUploadPath());
            const chip = page.getByTestId('composer-attached-file').first();
            const named = page.getByText('pico-plus-attach-tiny.txt');
            const chipVisible =
              (await chip.isVisible().catch(() => false)) ||
              (await named.isVisible().catch(() => false));
            report.p3 = chipVisible ? 'Y' : 'N';
          }
        } catch (err) {
          report.p2_error = String(err?.message || err).slice(0, 240);
        }
      } else {
        report.p2_error = 'composer-plus-attach missing';
      }
    } else {
      report.p2_error = 'plus menu not visible (likely clipped)';
    }
    const p3Path = path.join(out, 'P3-chip-1280.png');
    const s3 = await shot(page, p3Path, { allowSmall: true });
    report.p3_frame = { size: s3.size, sha: sha256(p3Path) };

    await page.setViewportSize({ width: 390, height: 844 });
    await goNewChat(page, base);
    const plus390 = page.getByTestId('composer-plus');
    await plus390.waitFor({ state: 'visible', timeout: 20000 });
    await plus390.click();
    const menu390 = await page.getByTestId('composer-plus-menu').boundingBox().catch(() => null);
    const p4Path = path.join(out, 'P4-plus-menu-390.png');
    const s4 = await shot(page, p4Path, { allowSmall: true });
    report.p4_menu_box = menu390;
    report.p4_frame = { size: s4.size, sha: sha256(p4Path) };
    report.p4 = menu390 && menu390.height > 20 ? 'Y' : 'N';

    writeJson(path.join(out, 'report.json'), report);
    console.log(JSON.stringify(report, null, 2));
    if (PHASE === 'after' && (report.p1 !== 'Y' || report.p3 !== 'Y')) {
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
