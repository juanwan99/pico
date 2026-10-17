#!/usr/bin/env node
/**
 * pico#1328 acceptance, one run against a live school (drill accounts only):
 *   ① a finished run shows 已完成 in the sidebar within 2 s (5 fresh chats, worst case)
 *   ② the right-hand web pane under a Chinese IME: 你好 lands as 2 characters, 677294 key by key
 *      lands once (the page echoes its input value into the window title, read back from Pico)
 *   ③ with nothing running the sidebar polls /v1/tasks at most 4 times a minute
 *
 *   PW_PASSWORD=... node scripts/pico-sidebar-ime-check.mjs --base https://edu.weiyuji.cn --login drill.t701
 *
 * Flags: --school 建校演练校  --runs 5  --out /tmp/pico-sidebar-ime  --only 1,2,3
 * Playwright comes from PW_MODULE (default "playwright"). Exits 1 on any ❌.
 */
import fs from 'node:fs';
import path from 'node:path';

const arg = (name, dflt) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : dflt;
};
const BASE = arg('base', 'https://edu.weiyuji.cn').replace(/\/$/, '');
const LOGIN = arg('login', 'drill.t701');
const SCHOOL = arg('school', '建校演练校');
const RUNS = Number(arg('runs', '5'));
const OUT = arg('out', '/tmp/pico-sidebar-ime');
const ONLY = new Set(arg('only', '1,2,3').split(','));
const PASSWORD = process.env.PW_PASSWORD || '';
if (!PASSWORD) {
  console.error('PW_PASSWORD is required');
  process.exit(2);
}
const { chromium } = await import(process.env.PW_MODULE || 'playwright');
fs.mkdirSync(OUT, { recursive: true });

// Fresh test data per run: a one-off tag and a test page that echoes its input into the title.
const tag = Math.random().toString(36).slice(2, 7);
const pageHtml =
  `<!doctype html><meta charset="utf-8"><title>v=</title>` +
  `<input id="c" autofocus style="font-size:40px;width:90%;height:300px" ` +
  `oninput="document.title='v='+this.value"><p>对账 ${tag}</p>`;
// httpbin wants url-safe base64 with its = padding kept.
const pageUrl = `https://httpbin.org/base64/${Buffer.from(pageHtml).toString('base64').replace(/\+/g, '-').replace(/\//g, '_')}`;

const results = [];
const record = (name, ok, detail) => {
  results.push({ name, ok, detail });
  console.log(`${ok ? '✅' : '❌'} ${name}：${detail}`);
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const edu = await ctx.newPage();
await edu.goto(`${BASE}/`);
await edu.locator('input:not([type=password])').first().fill(LOGIN);
await edu.locator('input[type=password]').fill(PASSWORD);
await edu.locator('button[type=submit]').click();
await edu.waitForTimeout(4000);
const pick = edu.getByText(SCHOOL, { exact: true });
if (await pick.count()) {
  await pick.first().click();
  await edu.waitForTimeout(3000);
}
if (process.env.CHECK_DEBUG) {
  ctx.on('response', (r) => {
    if (/\/api\/(auth|v1\/schools\/[^/]+\/pico)|\/login|\/c\//.test(r.url())) {
      console.log('  ', r.status(), r.request().method(), r.url().replace(/ticket=[^&]+/, 'ticket=…').slice(0, 140));
    }
  });
}
// The jump lands on an SSO hop first; the workbench is ready once its composer shows.
// Now and then the popup stays on Pico's login page (edu sets its location after the ticket
// arrives, which the browser may refuse); then finish the hop with that same ticket.
const composer = (page) => page.locator('#prompt-textarea, textarea:not([data-testid="sandbox-web-type"])').first();
let ticket = '';
edu.on('response', async (r) => {
  if (/\/pico\/web-ticket$/.test(new URL(r.url()).pathname)) {
    ticket = (await r.json().catch(() => ({}))).ticket || ticket;
  }
});
const [pico] = await Promise.all([ctx.waitForEvent('page'), edu.click('[data-testid="nav-pico-jump"]')]);
try {
  await composer(pico).waitFor({ timeout: 30000 });
} catch {
  console.log(`  跳转停在 ${new URL(pico.url()).pathname}，用同一张票补跳`);
  await pico.goto(`${new URL(pico.url()).origin}/api/auth/edu-sso?ticket=${encodeURIComponent(ticket)}`);
  await composer(pico).waitFor({ timeout: 60000 });
}
const picoOrigin = new URL(pico.url()).origin;

const taskPolls = [];
let picoHeaders = null;
pico.on('request', (req) => {
  const url = req.url();
  if (req.method() === 'GET' && /\/api\/pico\/v1\/tasks(\?|$)/.test(url)) {
    taskPolls.push(Date.now());
    picoHeaders = picoHeaders || req.headers();
  }
});
const sent = [];
pico.on('request', (req) => {
  if (req.method() === 'POST' && /\/api\/pico\/v1\/sandbox\/sessions\/[^/]+\/input/.test(req.url())) {
    try {
      const body = JSON.parse(req.postData() || '{}');
      if (body.text) {
        sent.push(body.text);
      }
    } catch {
      /* not json */
    }
  }
});

const prompt = () => composer(pico);
// The composer's own stop button marks the stream; 停止云端任务 (task-stop-button) is the cloud run.
const stopButton = () => pico.locator('[data-testid="stop-generation-button"]');
async function ask(text, timeoutMs = 300000) {
  await prompt().waitFor({ timeout: 60000 });
  await prompt().fill(text);
  await pico.keyboard.press('Enter');
  const t0 = Date.now();
  while (Date.now() - t0 < 15000 && !(await stopButton().count())) {
    await sleep(100);
  }
  while (Date.now() - t0 < timeoutMs && (await stopButton().count())) {
    await sleep(100);
  }
  return Date.now();
}
// The new chat's title is its first message, so the needle finds its row (null = not listed yet).
async function rowStatus(needle) {
  const rows = pico.locator('[data-testid="convo-item"]');
  const n = await rows.count();
  for (let i = 0; i < n; i++) {
    const row = rows.nth(i);
    if ((await row.innerText()).includes(needle)) {
      const s = row.locator('[data-testid="convo-ledger-status"]');
      return (await s.count()) ? (await s.innerText()).trim() : '';
    }
  }
  return null;
}

// ① stream end → 已完成 in the sidebar
if (ONLY.has('1')) {
  const gaps = [];
  for (let i = 1; i <= RUNS; i++) {
    await pico.goto(`${picoOrigin}/c/new`);
    await pico.waitForTimeout(3000);
    const needle = `对账${tag}${i}`;
    const ended = await ask(`只回一个字：好（${needle}）`, 120000);
    const atEnd = await rowStatus(needle);
    if (process.env.CHECK_DEBUG) {
      console.log(`  run ${i} 流结束时这一行：${atEnd === null ? '不在侧栏' : `「${atEnd}」`}`);
    }
    let gap = null;
    while (Date.now() - ended < 30000) {
      if ((await rowStatus(needle)) === '已完成') {
        gap = (Date.now() - ended) / 1000;
        break;
      }
      await sleep(100);
    }
    gaps.push(gap);
    console.log(`  run ${i}: ${gap === null ? '30 s 内没变' : `${gap.toFixed(1)} s`}`);
  }
  const worst = gaps.some((g) => g === null) ? null : Math.max(...gaps);
  record(
    '流结束到侧栏「已完成」≤ 2 s',
    worst !== null && worst <= 2,
    `${RUNS} 次 ${gaps.map((g) => (g === null ? '>30' : g.toFixed(1))).join(' / ')} s，最大 ${worst === null ? '>30' : worst.toFixed(1)} s`,
  );
}

// ② IME into the right-hand web pane
if (ONLY.has('2')) {
  await pico.goto(`${picoOrigin}/c/new`);
  await pico.waitForTimeout(3000);
  await ask(`在沙箱打开网页 ${pageUrl}`, 300000);
  const pane = pico.locator('[data-testid="sandbox-web-pane"][data-live="live"]');
  await pane.waitFor({ timeout: 60000 });
  const view = pico.locator('[data-testid="sandbox-web-viewport"]');
  await view.waitFor({ timeout: 60000 });
  const box = await view.boundingBox();
  await pico.mouse.click(box.x + box.width * 0.3, box.y + Math.min(box.height * 0.15, 150));
  await pico.waitForTimeout(1500);
  const typer = pico.locator('[data-testid="sandbox-web-type"]');
  await typer.focus();
  const cdp = await ctx.newCDPSession(pico);
  const readTitle = async () => {
    const m = /\/sandbox\/sessions\/([^/?]+)/.exec(
      (await pico.evaluate(() => performance.getEntriesByType('resource').map((e) => e.name).join('\n'))) || '',
    );
    if (!m || !picoHeaders) {
      return '';
    }
    const res = await ctx.request.get(`${picoOrigin}/api/pico/v1/sandbox/sessions/${m[1]}`, {
      headers: { authorization: picoHeaders.authorization || '' },
    });
    const meta = res.ok() ? await res.json() : {};
    if (process.env.CHECK_DEBUG) {
      console.log('  meta', res.status(), JSON.stringify(meta).slice(0, 400));
    }
    const titles = [meta.title, ...(meta.windows || []).map((w) => w.title)].filter(Boolean);
    return titles.find((t) => String(t).startsWith('v=')) || '';
  };
  // Pinyin composition, then commit 你好 (Chrome fires compositionend + input like a real IME).
  sent.length = 0;
  await cdp.send('Input.imeSetComposition', { text: 'nihao', selectionStart: 5, selectionEnd: 5 });
  await cdp.send('Input.insertText', { text: '你好' });
  await pico.waitForTimeout(2500);
  const afterHello = await readTitle();
  const sentHello = sent.join('');
  // Digits the way an IME delivers them: a keydown carrying the key, then the IME's own insert.
  sent.length = 0;
  for (const d of '677294') {
    const vk = d.charCodeAt(0);
    await cdp.send('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: d, code: `Digit${d}`, windowsVirtualKeyCode: vk });
    await cdp.send('Input.insertText', { text: d });
    await cdp.send('Input.dispatchKeyEvent', { type: 'keyUp', key: d, code: `Digit${d}`, windowsVirtualKeyCode: vk });
    await pico.waitForTimeout(150);
  }
  await pico.waitForTimeout(2500);
  const afterDigits = await readTitle();
  const sentDigits = sent.join('');
  await pico.screenshot({ path: path.join(OUT, 'ime-pane.png') });
  record(
    '输入法上屏「你好」正好 2 个字',
    sentHello === '你好' && (!afterHello || afterHello === 'v=你好'),
    `送进隔离网页「${sentHello}」，页面标题「${afterHello || '读不到'}」`,
  );
  record(
    '逐个按 677294 不双发',
    sentDigits === '677294' && (!afterDigits || afterDigits === 'v=你好677294'),
    `送进隔离网页「${sentDigits}」，页面标题「${afterDigits || '读不到'}」`,
  );
}

// ③ idle polling
if (ONLY.has('3')) {
  await pico.goto(`${picoOrigin}/c/new`);
  await pico.waitForTimeout(25000); // let any fast poll from the last run settle
  const from = Date.now();
  await pico.waitForTimeout(60000);
  const n = taskPolls.filter((t) => t >= from).length;
  record('没在运行时 /v1/tasks 每分钟 ≤ 4 次', n <= 4, `60 s 里 ${n} 次`);
}

await browser.close();
fs.writeFileSync(path.join(OUT, 'result.json'), JSON.stringify({ base: BASE, login: LOGIN, tag, results }, null, 1));
const bad = results.filter((r) => !r.ok).length;
console.log(`${results.length - bad}/${results.length} ✅ · 测试数据 ${tag} · ${OUT}`);
process.exit(bad ? 1 : 0);
