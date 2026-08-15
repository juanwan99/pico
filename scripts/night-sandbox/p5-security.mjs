#!/usr/bin/env node
/**
 * P5 teacher: metadata deny, cross-account 403, 9th desk refused, idle reclaim ps.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import {
  ROOT,
  loadPlaywright,
  loadEvidenceEnv,
  emailPass,
  fetchTip,
  shot,
  login,
  goNewChat,
  sendPrompt,
  writeJson,
} from './lib.mjs';

loadEvidenceEnv();

function parseArgs(argv) {
  const out = {
    base: process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia',
    out: process.env.PICO_NIGHT_OUT || path.join(ROOT, 'docs/evidence/pack-night-sandbox/p5'),
    timeoutMs: Number(process.env.PICO_VISUAL_TIMEOUT_MS || 120000),
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--base') out.base = next();
    else if (a === '--out') out.out = next();
    else throw new Error(`unknown arg: ${a}`);
  }
  return out;
}

function ecs(cmd) {
  return execFileSync('ssh', ['-o', 'BatchMode=yes', 'ecs', cmd], {
    encoding: 'utf8',
    timeout: 60000,
  });
}

function sandboxPs() {
  return ecs(
    "docker exec pico-pico-sandbox-1 sh -c 'ps -ef | grep -E \"chrome|chromium|soffice\" | grep -v grep | wc -l; echo ---; free -h | head -2'",
  );
}

async function waitBody(page, re, timeoutMs) {
  const start = Date.now();
  let last = '';
  while (Date.now() - start < timeoutMs) {
    last = await page.locator('body').innerText().catch(() => '');
    if (re.test(last)) return last;
    await page.waitForTimeout(600);
  }
  throw new Error(`did not see ${re}: ${last.slice(0, 220)}`);
}

async function main() {
  const args = parseArgs(process.argv);
  const { email, password } = emailPass();
  if (!email || !password) throw new Error('DEMO_EMAIL missing');
  let tip = null;
  try {
    tip = await fetchTip(args.base);
  } catch (err) {
    tip = { error: String(err?.message || err) };
  }
  const report = {
    card: 'T-NIGHT-SANDBOX-COMPUTER',
    phase: 'P5',
    base: args.base,
    tip,
    s12: 'N',
    s13: 'N',
    s14: 'N',
    s15: 'N',
    claim_wb: 'NO',
  };
  const { chromium } = loadPlaywright();
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const fillers = [];
  try {
    const context = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const page = await context.newPage();
    let capturedSession = '';
    page.on('response', async (res) => {
      try {
        if (!/\/v1\/sandbox\/sessions/.test(res.url()) || res.request().method() !== 'POST') {
          return;
        }
        const json = await res.json();
        if (json?.session_id) capturedSession = String(json.session_id);
      } catch {
        /* ignore */
      }
    });
    await login(page, args.base, email, password);
    await goNewChat(page, args.base);
    await sendPrompt(page, '打开 http://169.254.169.254/latest/meta-data/');
    const s12Text = await waitBody(
      page,
      /不能|拒绝|denied|无权|仅支持|公网/i,
      args.timeoutMs,
    );
    if (/ami-id|instance-id|computeMetadata/i.test(s12Text)) {
      throw new Error('S12: metadata body leaked');
    }
    const s12 = await shot(page, path.join(args.out, 'S12-metadata-deny.png'));
    report.s12 = 'Y';
    report.s12_bytes = s12.size;

    await goNewChat(page, args.base);
    await sendPrompt(page, '打开 https://example.com');
    await waitBody(page, /Example Domain|sandbox-web-pane|隔离/i, args.timeoutMs);
    const start = Date.now();
    while (!capturedSession && Date.now() - start < 45000) {
      await page.waitForTimeout(500);
    }
    if (!capturedSession) {
      throw new Error('S13: did not capture owner session_id');
    }
    const bContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const bPage = await bContext.newPage();
    const bEmail = `night-p5-b-${Date.now()}@example.com`;
    const bPass = 'NightP5pass!234';
    await bPage.goto(new URL('/register', args.base).toString(), { waitUntil: 'domcontentloaded' });
    await bPage.waitForTimeout(600);
    if (await bPage.getByLabel(/Email|邮箱/i).count()) {
      await bPage.getByLabel(/Email|邮箱/i).first().fill(bEmail);
      await bPage.getByLabel(/Password|密码/i).first().fill(bPass);
      const confirm = bPage.getByLabel(/Confirm|确认/i);
      if (await confirm.count()) await confirm.first().fill(bPass);
    } else {
      await bPage.locator('input[type="email"], input[name="email"]').first().fill(bEmail);
      const passes = bPage.locator('input[type="password"]');
      await passes.nth(0).fill(bPass);
      if ((await passes.count()) > 1) await passes.nth(1).fill(bPass);
    }
    const submit = bPage.getByRole('button', { name: /[Cc]ontinue|[Rr]egister|注册|Sign up/i });
    if (await submit.count()) await submit.first().click();
    else await bPage.locator('button[type="submit"]').first().click();
    await bPage.waitForTimeout(2000);
    if (bPage.url().includes('login') || (await bPage.getByLabel(/Password|密码/i).count())) {
      await login(bPage, args.base, bEmail, bPass);
    }
    const shotRes = await bPage.evaluate(async (sessionId) => {
      const res = await fetch(`/api/pico/v1/sandbox/sessions/${sessionId}/screenshot`, {
        credentials: 'include',
        cache: 'no-store',
      });
      const text = await res.text();
      return { status: res.status, text: text.slice(0, 180) };
    }, capturedSession);
    fs.writeFileSync(
      path.join(args.out, 'S13-cross-account.json'),
      `${JSON.stringify({ owner: capturedSession, ...shotRes }, null, 2)}\n`,
    );
    if (shotRes.status !== 403) {
      throw new Error(`S13: expected 403 got ${shotRes.status} ${shotRes.text}`);
    }
    await shot(bPage, path.join(args.out, 'S13-b-denied.png'), { allowSmall: true }).catch(() => {});
    report.s13 = 'Y';
    report.s13_status = shotRes.status;
    await bContext.close();

    const psBeforeFill = sandboxPs();
    fs.writeFileSync(path.join(args.out, 'S14-ps-before.txt'), psBeforeFill);
    for (let i = 0; i < 8; i++) {
      const raw = ecs(
        `curl -sS -m 40 -X POST http://127.0.0.1:18767/v1/internal/sessions/open -H 'content-type: application/json' -d '{"school_id":"cap","membership_id":"cap-${i}","url":"https://example.com/"}'`,
      );
      fillers.push(raw);
    }
    const cContext = await browser.newContext({
      viewport: { width: 1280, height: 800 },
      ignoreHTTPSErrors: true,
    });
    const cPage = await cContext.newPage();
    const cEmail = `night-p5-c-${Date.now()}@example.com`;
    const cPass = 'NightP5pass!234';
    await cPage.goto(new URL('/register', args.base).toString(), { waitUntil: 'domcontentloaded' });
    await cPage.waitForTimeout(600);
    if (await cPage.getByLabel(/Email|邮箱/i).count()) {
      await cPage.getByLabel(/Email|邮箱/i).first().fill(cEmail);
      await cPage.getByLabel(/Password|密码/i).first().fill(cPass);
      const confirm = cPage.getByLabel(/Confirm|确认/i);
      if (await confirm.count()) await confirm.first().fill(cPass);
    } else {
      await cPage.locator('input[type="email"], input[name="email"]').first().fill(cEmail);
      const passes = cPage.locator('input[type="password"]');
      await passes.nth(0).fill(cPass);
      if ((await passes.count()) > 1) await passes.nth(1).fill(cPass);
    }
    const cSubmit = cPage.getByRole('button', { name: /[Cc]ontinue|[Rr]egister|注册|Sign up/i });
    if (await cSubmit.count()) await cSubmit.first().click();
    else await cPage.locator('button[type="submit"]').first().click();
    await cPage.waitForTimeout(1500);
    if (cPage.url().includes('login') || (await cPage.getByLabel(/Password|密码/i).count())) {
      await login(cPage, args.base, cEmail, cPass);
    }
    await goNewChat(cPage, args.base);
    await sendPrompt(cPage, '打开 https://example.com');
    const s14Text = await waitBody(cPage, /已满|最多 8|quota/i, args.timeoutMs);
    const s14 = await shot(cPage, path.join(args.out, 'S14-ninth-refused.png'));
    await cContext.close();
    const free = ecs('free -h');
    fs.writeFileSync(path.join(args.out, 'S14-free.txt'), free);
    if (/已满|8/.test(s14Text) === false) {
      throw new Error('S14: ninth desk not refused in UI');
    }
    report.s14 = 'Y';
    report.s14_bytes = s14.size;

    const psBefore = sandboxPs();
    fs.writeFileSync(path.join(args.out, 'S15-ps-before.txt'), psBefore);
    const beforeN = Number((psBefore.split('\n')[0] || '0').trim());
    for (let i = 0; i < 8; i++) {
      try {
        const sid = JSON.parse(fillers[i] || '{}').session_id;
        if (!sid) continue;
        ecs(
          `curl -sS -m 10 -X POST 'http://127.0.0.1:18767/v1/internal/sessions/${sid}/destroy?school_id=cap&membership_id=cap-${i}'`,
        );
      } catch {
        /* continue */
      }
    }
    await page.waitForTimeout(1500);
    const psAfter = sandboxPs();
    fs.writeFileSync(path.join(args.out, 'S15-ps-after.txt'), psAfter);
    const afterN = Number((psAfter.split('\n')[0] || '0').trim());
    if (!(afterN < beforeN)) {
      throw new Error(`S15: process count did not drop (${beforeN} -> ${afterN})`);
    }
    report.s15 = 'Y';
    report.s15_ps_before = beforeN;
    report.s15_ps_after = afterN;
    report.verdict = 'PASS';
  } catch (err) {
    report.verdict = 'FAIL';
    report.error = String(err?.message || err);
    throw err;
  } finally {
    writeJson(path.join(args.out, 'REPORT.json'), report);
    await browser.close();
  }
  console.log(JSON.stringify(report, null, 2));
}

main().catch((err) => {
  console.error(`## BLOCKED P5\n${err.message || err}`);
  process.exit(2);
});
