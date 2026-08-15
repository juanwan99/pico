#!/usr/bin/env node
/**
 * T-UX-SANDBOX-CHROME human Playwright: U1 idle composer, U2 example.com
 * screen, U3 dead session, U4 390 close. Live public after tip install.
 */
import fs from 'node:fs';
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

const EXPECT = process.env.PICO_EXPECT_TIP || '';

function sha256(filePath) {
  return crypto.createHash('sha256').update(fs.readFileSync(filePath)).digest('hex');
}

async function waitSandbox(page, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    const pane = page.getByTestId('sandbox-web-pane');
    if (await pane.count()) {
      last = `${await pane.innerText().catch(() => '')}`;
      const live = await pane.getAttribute('data-live').catch(() => '');
      const hasView = await page.getByTestId('sandbox-web-viewport').count();
      if (live !== 'dead' && hasView) {
        return last;
      }
    }
    await page.waitForTimeout(800);
  }
  throw new Error(`sandbox viewport not visible: ${last.slice(0, 240)}`);
}

async function main() {
  const base = process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia';
  const out = path.join(ROOT, 'docs/evidence/pack-ux-sandbox-chrome/live');
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
    card: 'T-UX-SANDBOX-CHROME',
    tip,
    u1: 'N',
    u2: 'N',
    u3: 'N',
    u4: 'N',
    claim_wb: 'NO',
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    await login(page, base, email, password);
    await goNewChat(page, base);

    const bodyText = await page.locator('body').innerText();
    if (/调用技能与指令/.test(bodyText)) {
      throw new Error('U1: 调用技能与指令 still visible');
    }
    const plus = page.getByTestId('composer-plus');
    await plus.waitFor({ state: 'visible', timeout: 20000 });
    const u1 = path.join(out, 'u1-idle-1280.png');
    const s1 = await shot(page, u1);
    report.u1 = 'Y';
    report.u1_size = s1.size;
    report.u1_sha = sha256(u1);

    await sendPrompt(page, '打开 https://example.com');
    await waitSandbox(page, Number(process.env.PICO_VISUAL_TIMEOUT_MS || 120000));
    await page.waitForTimeout(1200);
    if (await page.getByTestId('pico-search-sources').count()) {
      throw new Error('U2: 来源 still on sandbox');
    }
    if (await page.getByTestId('sandbox-login-form').count()) {
      throw new Error('U2: login form on example.com');
    }
    if (await page.getByText('打开我的文件', { exact: true }).count()) {
      throw new Error('U2: 打开我的文件 still visible');
    }
    const u2 = path.join(out, 'u2-example-1280.png');
    const s2 = await shot(page, u2);
    report.u2 = 'Y';
    report.u2_size = s2.size;
    report.u2_sha = sha256(u2);

    const closeKeep = page.getByTestId('sandbox-close-keep-disk');
    if (await closeKeep.count()) {
      await page.getByTestId('sandbox-screen-menu').click();
      await closeKeep.click();
    } else {
      await page.evaluate(async () => {
        const pane = document.querySelector('[data-testid="sandbox-web-pane"]');
        const sid = pane?.getAttribute('data-session') || '';
        if (!sid) {
          const res = await fetch('/api/pico/v1/sandbox/sessions', { credentials: 'include' });
          return res.status;
        }
        return sid;
      });
    }
    const dead = page.getByTestId('sandbox-dead');
    if (await closeKeep.count()) {
      await page.getByTestId('sandbox-screen-menu').click().catch(() => {});
      await page.getByTestId('sandbox-close-keep-disk').click().catch(() => {});
    }
    // destroy via API if UI menu already closed the window
    await page.waitForTimeout(1500);
    if (!(await dead.count())) {
      await page.evaluate(async () => {
        const matches = document.body.innerHTML.match(/sbox_[A-Za-z0-9_-]{8,}/);
        const sid = matches?.[0];
        if (!sid) {
          return;
        }
        await fetch(`/api/pico/v1/sandbox/sessions/${sid}`, {
          method: 'DELETE',
          credentials: 'include',
        });
      });
      await page.waitForTimeout(2000);
    }
    await dead.waitFor({ state: 'visible', timeout: 20000 });
    if (await page.getByTestId('sandbox-login-form').count()) {
      throw new Error('U3: login form on dead session');
    }
    await page.getByTestId('sandbox-reopen').waitFor({ state: 'visible' });
    const u3 = path.join(out, 'u3-dead-1280.png');
    const s3 = await shot(page, u3);
    report.u3 = 'Y';
    report.u3_size = s3.size;
    report.u3_sha = sha256(u3);

    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(400);
    const u4 = path.join(out, 'u4-390.png');
    const s4 = await shot(page, u4, { allowSmall: false });
    const composerBox = await page.getByTestId('composer-plus').boundingBox();
    if (composerBox && composerBox.x + composerBox.width > 400) {
      throw new Error('U4: composer stretches past 390');
    }
    const close = page.getByTestId('result-panel-close');
    if (await close.count()) {
      await close.click();
      await page.getByTestId('result-panel-toggle').waitFor({ state: 'visible', timeout: 8000 });
    }
    report.u4 = 'Y';
    report.u4_size = s4.size;
    report.u4_sha = sha256(u4);

    const hashes = [report.u1_sha, report.u2_sha, report.u3_sha];
    if (new Set(hashes).size !== 3) {
      throw new Error('U1/U2/U3 hashes not distinct');
    }
    writeJson(path.join(out, 'report.json'), report);
    console.log(JSON.stringify(report, null, 2));
  } finally {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
