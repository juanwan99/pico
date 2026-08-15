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
    "echo COUNT=$(ps -ef | grep -E 'chrome|chromium|soffice|Xvfb' | grep -v grep | wc -l); echo ---; free -h | head -2; echo ---; ps -ef | grep -E 'chrome|chromium|soffice|Xvfb' | grep -v grep | wc -l",
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
    const bProbe = ecs(
      `curl -sS -m 10 -o /tmp/p5-b.png -w '%{http_code}' 'http://127.0.0.1:18767/v1/internal/sessions/${capturedSession}/png?school_id=school-a&membership_id=night-p5-outsider'`,
    ).trim();
    const shotPayload = {
      status: Number(bProbe.slice(-3)),
      text: bProbe,
      via: 'sidecar-wrong-membership',
    };
    fs.writeFileSync(
      path.join(args.out, 'S13-cross-account.json'),
      `${JSON.stringify({ owner: capturedSession, ...shotPayload }, null, 2)}\n`,
    );
    if (shotPayload.status !== 403) {
      throw new Error(`S13: expected 403 got ${shotPayload.status} ${shotPayload.text}`);
    }
    report.s13 = 'Y';
    report.s13_status = shotPayload.status;

    const psBeforeFill = sandboxPs();
    fs.writeFileSync(path.join(args.out, 'S14-ps-before.txt'), psBeforeFill);
    for (let i = 0; i < 8; i++) {
      const raw = ecs(
        `curl -sS -m 40 -X POST http://127.0.0.1:18767/v1/internal/sessions/open -H 'content-type: application/json' -d '{"school_id":"cap","membership_id":"cap-${i}","url":"https://example.com/"}'`,
      );
      fillers.push(raw);
    }
    const ninth = ecs(
      `curl -sS -m 20 -X POST http://127.0.0.1:18767/v1/internal/sessions/open -H 'content-type: application/json' -d '{"school_id":"cap","membership_id":"cap-ninth","url":"https://example.com/"}'`,
    );
    fs.writeFileSync(path.join(args.out, 'S14-ninth.json'), `${ninth}\n`);
    await goNewChat(page, args.base);
    await sendPrompt(page, '打开 https://example.org');
    await page.waitForTimeout(2500);
    const s14 = await shot(page, path.join(args.out, 'S14-ninth-refused.png'));
    const free = ecs('free -h');
    fs.writeFileSync(path.join(args.out, 'S14-free.txt'), free);
    if (!/quota|已满|最多 8/.test(ninth)) {
      throw new Error(`S14: ninth desk not refused: ${ninth.slice(0, 220)}`);
    }
    report.s14 = 'Y';
    report.s14_bytes = s14.size;

    const psBefore = sandboxPs();
    fs.writeFileSync(path.join(args.out, 'S15-ps-before.txt'), psBefore);
    const beforeN = Number((psBefore.match(/COUNT=(\d+)/) || [0, '0'])[1]);
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
    const afterN = Number((psAfter.match(/COUNT=(\d+)/) || [0, '0'])[1]);
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
