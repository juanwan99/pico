#!/usr/bin/env node
/**
 * BINDING #384 visual gate — public human-path capture (V0–V3).
 *
 * Shared by Grok / DeepSeek / CI-ish local runs. One script only.
 * Does NOT claim CLAIM-WB or product Ready. PNG + manifest are evidence only.
 *
 * Usage:
 *   set -a; . ~/.secrets/pico-r4r6-evidence.env; set +a
 *   NODE_PATH="$HOME/.npm-global/lib/node_modules${NODE_PATH:+:$NODE_PATH}" \
 *     node scripts/visual-gate.mjs \
 *       --card T-DEMO --scene smoke \
 *       --prompt '只回一句：视觉门OK，不要调用工具'
 *
 * Env:
 *   DEMO_EMAIL / DEMO_PASSWORD  or  PICO_E2E_EMAIL / PICO_E2E_PASSWORD
 *   PICO_PUBLIC_BASE   default https://pico.aivia.asia
 *   PICO_VISUAL_CARD / PICO_VISUAL_SCENE / PICO_VISUAL_PROMPT
 *   PICO_VISUAL_OUT    default docs/evidence/<card>/<scene>
 *   PICO_VISUAL_TIMEOUT_MS  default 240000 (agent finish wait)
 *   PICO_VISUAL_HEADED=1    headed chromium
 */
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');

function loadPlaywright() {
  const require = createRequire(import.meta.url);
  const candidates = [
    path.join(ROOT, 'node_modules', 'playwright'),
    path.join(ROOT, 'apps', 'librechat', 'node_modules', 'playwright'),
    path.join(process.env.HOME || '', '.npm-global', 'lib', 'node_modules', 'playwright'),
    'playwright',
  ];
  for (const c of candidates) {
    try {
      return require(c);
    } catch {
      /* next */
    }
  }
  throw new Error(
    'playwright not found. Install globally (npm i -g playwright) or set NODE_PATH to node_modules.',
  );
}

const { chromium } = loadPlaywright();

// #384 / #394 main-bubble one-strike patterns (fail-soft heuristic; human still reads PNGs)
const MONOLOGUE_RES = [
  /\bgenerate_(?:html|docx|pptx)_document\b/i,
  /\bworkspace_write(?:_file)?\b/i,
  /\bartifact_id\b/i,
  /\bverification_level\b/i,
  /\bmin_required\b/i,
  /\bmin_artifacts\b/i,
  /\bJSON\s*escape\b/i,
  /"body"\s*:\s*"/i,
  /\bLet me (?:build|construct|call)\b/i,
  /我先构造\s*tool/i,
  /\btool\s*参数\b/i,
  // #394/#399 — L0 / structure self-check + EN system-side engineer wall
  /结构自检|静态自检|系统侧|二进制编码|未做浏览器真机|未经真机点击|未宣称\s*L1|L0_structure|interaction_status/i,
  /system-side\s+verification|let me run the system-side/i,
  /\bI'll create\b.*\bHTML\b/i,
];

function parseArgs(argv) {
  const out = {
    card: process.env.PICO_VISUAL_CARD || 'visual-gate',
    scene: process.env.PICO_VISUAL_SCENE || 'default',
    prompt:
      process.env.PICO_VISUAL_PROMPT ||
      '只回一句：视觉门OK，不要调用工具，不要输出代码。',
    base: process.env.PICO_PUBLIC_BASE || 'https://pico.aivia.asia',
    out: process.env.PICO_VISUAL_OUT || '',
    timeoutMs: Number(process.env.PICO_VISUAL_TIMEOUT_MS || 240000),
    headed: process.env.PICO_VISUAL_HEADED === '1',
    skipProduct: process.env.PICO_VISUAL_SKIP_V3 === '1',
    help: false,
  };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--help' || a === '-h') out.help = true;
    else if (a === '--card') out.card = next();
    else if (a === '--scene') out.scene = next();
    else if (a === '--prompt') out.prompt = next();
    else if (a === '--base') out.base = next();
    else if (a === '--out') out.out = next();
    else if (a === '--timeout-ms') out.timeoutMs = Number(next());
    else if (a === '--headed') out.headed = true;
    else if (a === '--skip-v3') out.skipProduct = true;
    else throw new Error(`unknown arg: ${a}`);
  }
  return out;
}

function emailPass() {
  const email = process.env.PICO_E2E_EMAIL || process.env.DEMO_EMAIL || '';
  const password = process.env.PICO_E2E_PASSWORD || process.env.DEMO_PASSWORD || '';
  return { email, password };
}

async function fetchTip(base) {
  const url = new URL('/api/pico/tip', base).toString();
  const res = await fetch(url, { redirect: 'follow' });
  const text = await res.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error(`tip not JSON http=${res.status}: ${text.slice(0, 120)}`);
  }
  if (!json?.ok || !json?.git_sha || !/^[0-9a-f]{40}$/.test(json.git_sha)) {
    throw new Error(`tip invalid: ${text.slice(0, 200)}`);
  }
  return { url, ...json };
}

function ensureDir(d) {
  fs.mkdirSync(d, { recursive: true });
}

async function shot(page, filePath, opts = {}) {
  ensureDir(path.dirname(filePath));
  await page.screenshot({ path: filePath, fullPage: !!opts.fullPage, type: 'png' });
  return filePath;
}

async function mainBubbleText(page) {
  // Prefer assistant message bubbles only — NOT the right engineer sidebar
  // (tool names there are expected; #384 veto is main-bubble only).
  const prefer = [
    '[data-testid="message-content"]',
    '[data-testid="messages-view"] .markdown',
    '[data-testid="messages-view"]',
    'main [class*="message"]',
    'main',
  ];
  for (const sel of prefer) {
    const loc = page.locator(sel);
    const n = await loc.count();
    if (!n) continue;
    // Concat visible message texts (user + assistant), exclude empty.
    const parts = [];
    const limit = Math.min(n, 40);
    for (let i = 0; i < limit; i++) {
      const t = await loc.nth(i).innerText().catch(() => '');
      if (t && t.trim()) parts.push(t.trim());
    }
    if (parts.length) return parts.join('\n\n');
  }
  // Last resort: still avoid full body if possible
  return page.locator('main').innerText().catch(() => page.locator('body').innerText().catch(() => ''));
}

function scanMonologue(text) {
  const hits = [];
  for (const re of MONOLOGUE_RES) {
    if (re.test(text)) hits.push(re.toString());
  }
  return hits;
}

async function login(page, base, email, password) {
  const loginUrl = new URL('/login', base).toString();
  await page.goto(loginUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(800);

  // Already in app?
  if (await page.getByRole('textbox', { name: /Message input|消息/i }).count()) {
    return { already: true };
  }

  const emailBox = page.getByLabel(/Email|邮箱|电子邮件/i).first();
  const passBox = page.getByLabel(/Password|密码/i).first();
  if (!(await emailBox.count()) || !(await passBox.count())) {
    // Fallback test ids / placeholders
    const e2 = page.locator('input[type="email"], input[name="email"]').first();
    const p2 = page.locator('input[type="password"]').first();
    await e2.fill(email);
    await p2.fill(password);
  } else {
    await emailBox.fill(email);
    await passBox.fill(password);
  }

  const loginBtn = page.getByTestId('login-button');
  if (await loginBtn.count()) {
    await loginBtn.click();
  } else {
    await page.getByRole('button', { name: /[Ll]og ?in|登录|Sign in/i }).click();
  }

  await page.waitForURL(/\/(c\/|chat)/, { timeout: 45000 }).catch(() => {});
  await page.waitForTimeout(1500);
  return { already: false };
}

async function goNewChat(page, base) {
  const newUrl = new URL('/c/new', base).toString();
  await page.goto(newUrl, { waitUntil: 'domcontentloaded', timeout: 60000 });
  await page.waitForTimeout(1200);
  // dismiss modals if any
  const close = page.getByRole('button', { name: /close|关闭|Got it|知道了/i });
  if (await close.count()) {
    await close.first().click().catch(() => {});
  }
}

async function messageInput(page) {
  const byName = page.getByRole('textbox', { name: /Message input|消息/i });
  if (await byName.count()) return byName.first();
  const formBox = page.locator('form').getByRole('textbox');
  if (await formBox.count()) return formBox.first();
  return page.locator('[data-testid="text-input"], textarea').first();
}

async function sendPrompt(page, prompt) {
  const input = await messageInput(page);
  await input.click();
  await input.fill(prompt);
  await page.waitForTimeout(200);
  // Enter send (LibreChat default)
  await input.press('Enter');
}

async function waitSettled(page, timeoutMs) {
  const start = Date.now();
  let sawStreaming = false;
  let lastText = '';
  let stableSince = Date.now();

  while (Date.now() - start < timeoutMs) {
    const text = await mainBubbleText(page);
    const streaming =
      /生成中|思考中|正在|Stop|停止生成|Typing/i.test(text) ||
      (await page.getByRole('button', { name: /Stop|停止/i }).count()) > 0;

    if (streaming) {
      sawStreaming = true;
      stableSince = Date.now();
    } else if (text !== lastText) {
      lastText = text;
      stableSince = Date.now();
    } else if (Date.now() - stableSince > 4000) {
      // quiet for 4s after last text change → settled
      if (sawStreaming || (Date.now() - start > 8000 && text.length > 20)) {
        return { sawStreaming, text };
      }
    }
    lastText = text;
    await page.waitForTimeout(800);
  }
  return { sawStreaming, text: await mainBubbleText(page), timedOut: true };
}

async function inspectHtmlHumanPage(page) {
  // Prefer in-panel sandboxed preview iframe after 打开.
  const iframe = page.locator('[data-testid="artifact-html-iframe"]');
  if (await iframe.count()) {
    const handle = await iframe.elementHandle().catch(() => null);
    if (handle) {
      const frame = await handle.contentFrame().catch(() => null);
      if (frame) {
        const bodyText = await frame.locator('body').innerText().catch(() => '');
        const title = await frame.title().catch(() => '');
        const buttons = await frame.locator('button, input[type="button"], a.btn, [role="button"]').count().catch(() => 0);
        const headings = await frame.locator('h1, h2, h3, table, th').count().catch(() => 0);
        return {
          kind: 'html-iframe',
          title,
          body_snippet: (bodyText || '').slice(0, 240),
          button_count: buttons,
          structure_count: headings,
          human_page:
            Boolean((title && title.trim()) || (bodyText && bodyText.trim().length > 8)) &&
            (buttons > 0 || headings > 0 || /新增|导出|状态|事项|负责人|表格|button/i.test(bodyText || '')),
        };
      }
    }
    // iframe present but cross-origin opaque — still opened product UI.
    return {
      kind: 'html-iframe-present',
      human_page: true,
      note: 'iframe present; content opaque to automation',
    };
  }
  return null;
}

async function tryOpenProduct(page, outDir) {
  // #394 Y2 / #399 R1: V3 = opened human page. Prefer main-column delivery strip, then side panel.
  const openSelectors = [
    { testId: 'main-delivery-open', iframe: 'main-delivery-html-iframe', via: 'main-delivery-open' },
    { testId: 'artifact-open-button', iframe: 'artifact-html-iframe', via: 'artifact-open-button' },
  ];
  for (const sel of openSelectors) {
    const openBtn = page.getByTestId(sel.testId);
    if (!(await openBtn.count())) continue;
    await openBtn.first().click({ timeout: 8000 }).catch(() => null);
    await page.waitForTimeout(1500);
    await page
      .locator(
        `[data-testid="${sel.iframe}"], [data-testid="artifact-html-iframe"], [data-testid="main-delivery-html-iframe"], [data-testid="artifact-inline-preview"]`,
      )
      .first()
      .waitFor({ state: 'visible', timeout: 12000 })
      .catch(() => {});
    await page.waitForTimeout(800);
    const human = await inspectHtmlHumanPage(page);
    // Also accept main-column iframe
    let human2 = human;
    if (!human2) {
      const mainIframe = page.locator('[data-testid="main-delivery-html-iframe"]');
      if (await mainIframe.count()) {
        const handle = await mainIframe.elementHandle().catch(() => null);
        const frame = handle ? await handle.contentFrame().catch(() => null) : null;
        if (frame) {
          const bodyText = await frame.locator('body').innerText().catch(() => '');
          const title = await frame.title().catch(() => '');
          const buttons = await frame.locator('button').count().catch(() => 0);
          human2 = {
            kind: 'main-delivery-iframe',
            title,
            body_snippet: (bodyText || '').slice(0, 240),
            button_count: buttons,
            human_page: Boolean(title || (bodyText && bodyText.length > 8) || buttons > 0),
          };
        }
      }
    }
    await shot(page, path.join(outDir, 'V3-open-product.png'), { fullPage: true });
    const mainStrip = await page.getByTestId('main-delivery-strip').count();
    if (human2) {
      return {
        opened: true,
        via: sel.via,
        human_page: !!human2.human_page,
        main_delivery_strip: mainStrip > 0,
        preview: human2,
      };
    }
    return {
      opened: true,
      via: sel.via,
      human_page: false,
      main_delivery_strip: mainStrip > 0,
      note: 'open clicked; iframe not detected',
    };
  }

  // Fallback: links / download chips / generic open
  const candidates = [
    page.getByRole('link', { name: /\.(html?|md|docx?|pptx?|pdf|txt)$/i }),
    page.locator('a[download]'),
    page.getByRole('button', { name: /打开|Open/i }),
    page.getByRole('button', { name: /下载|Download/i }),
  ];
  for (const loc of candidates) {
    if (await loc.count()) {
      const first = loc.first();
      const box = await first.boundingBox().catch(() => null);
      if (!box) continue;
      const [popup] = await Promise.all([
        page.context().waitForEvent('page', { timeout: 5000 }).catch(() => null),
        first.click({ timeout: 5000 }).catch(() => null),
      ]);
      await page.waitForTimeout(1200);
      if (popup) {
        await popup.waitForLoadState('domcontentloaded').catch(() => {});
        const bodyText = await popup.locator('body').innerText().catch(() => '');
        const title = await popup.title().catch(() => '');
        const buttons = await popup.locator('button, input[type="button"]').count().catch(() => 0);
        await shot(popup, path.join(outDir, 'V3-open-product.png'), { fullPage: true });
        await popup.close().catch(() => {});
        return {
          opened: true,
          via: 'popup',
          human_page: Boolean(title || (bodyText && bodyText.length > 8) || buttons > 0),
          preview: { title, button_count: buttons, body_snippet: (bodyText || '').slice(0, 240) },
        };
      }
      const human = await inspectHtmlHumanPage(page);
      await shot(page, path.join(outDir, 'V3-open-product.png'), { fullPage: true });
      return {
        opened: true,
        via: 'same-tab',
        human_page: human ? !!human.human_page : false,
        preview: human || undefined,
      };
    }
  }
  // No product — still capture a frame stating empty results area
  await shot(page, path.join(outDir, 'V3-open-product.png'), { fullPage: true });
  return { opened: false, via: 'no-chip', human_page: false };
}

async function run() {
  const args = parseArgs(process.argv);
  if (args.help) {
    console.log(`visual-gate.mjs — BINDING #384 V0–V3 public capture
  --card NAME --scene NAME --prompt '...' [--base URL] [--out DIR]
  --timeout-ms N --headed --skip-v3
Env: DEMO_EMAIL DEMO_PASSWORD (or PICO_E2E_*) PICO_PUBLIC_BASE
`);
    process.exit(0);
  }

  const { email, password } = emailPass();
  if (!email || password.length < 12) {
    console.error(
      'BLOCKED: set DEMO_EMAIL + DEMO_PASSWORD (12+) or PICO_E2E_EMAIL/PASSWORD (see ~/.secrets/pico-r4r6-evidence.env)',
    );
    process.exit(2);
  }

  const outDir =
    args.out ||
    path.join(ROOT, 'docs', 'evidence', args.card, args.scene);
  ensureDir(outDir);

  const tip = await fetchTip(args.base);
  console.log(JSON.stringify({ step: 'tip', ...tip }, null, 0));

  const browser = await chromium.launch({
    headless: !args.headed,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });

  const frames = {};
  const notes = [];
  let monologueHits = [];
  let conversationUrl = '';
  let v3 = { opened: false };

  try {
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      locale: 'zh-CN',
    });
    const page = await context.newPage();

    await login(page, args.base, email, password);
    await goNewChat(page, args.base);

    const input = await messageInput(page);
    await input.waitFor({ state: 'visible', timeout: 30000 });

    // Fill for V0 (sent / about to send)
    await input.click();
    await input.fill(args.prompt);
    frames.V0 = await shot(page, path.join(outDir, 'V0-send.png'), { fullPage: true });
    await input.press('Enter');
    await page.waitForTimeout(1500);
    conversationUrl = page.url();

    // V1 process — poll mid-run
    let v1Taken = false;
    const v1Deadline = Date.now() + Math.min(args.timeoutMs, 90000);
    while (Date.now() < v1Deadline && !v1Taken) {
      const t = await mainBubbleText(page);
      const mid =
        t.length > args.prompt.length + 10 ||
        /生成|思考|工具|Stop|停止|…|\.\.\./i.test(t);
      if (mid) {
        frames.V1 = await shot(page, path.join(outDir, 'V1-process-main.png'), {
          fullPage: true,
        });
        monologueHits = scanMonologue(t);
        v1Taken = true;
        break;
      }
      await page.waitForTimeout(600);
    }
    if (!v1Taken) {
      frames.V1 = await shot(page, path.join(outDir, 'V1-process-main.png'), {
        fullPage: true,
      });
      notes.push('V1: no clear mid-stream chrome; captured best-effort process frame');
    }

    const settled = await waitSettled(page, args.timeoutMs);
    frames.V2 = await shot(page, path.join(outDir, 'V2-final.png'), { fullPage: true });
    const finalText = settled.text || (await mainBubbleText(page));
    monologueHits = [...new Set([...monologueHits, ...scanMonologue(finalText)])];

    if (!args.skipProduct) {
      v3 = await tryOpenProduct(page, outDir);
      frames.V3 = path.join(outDir, 'V3-open-product.png');
    } else {
      notes.push('V3 skipped (--skip-v3)');
    }

    // 390 viewport (at least one frame — use final)
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(500);
    frames.V2_390 = await shot(page, path.join(outDir, 'V2-final-390.png'), {
      fullPage: true,
    });

    conversationUrl = page.url();
  } finally {
    await browser.close();
  }

  const required = ['V0-send.png', 'V1-process-main.png', 'V2-final.png'];
  if (!args.skipProduct) required.push('V3-open-product.png');
  const missing = required.filter((f) => !fs.existsSync(path.join(outDir, f)));

  const manifest = {
    binding: 'ACCEPT-VISUAL-HUMAN-GATE #384',
    claim_wb: 'NO',
    product_ready: false,
    note:
      'Engineering evidence only. Missing frames or monologue hits ⇒ scene FAIL / 产品未过. CLAIM-WB only owner.',
    at: new Date().toISOString(),
    base: args.base,
    card: args.card,
    scene: args.scene,
    prompt: args.prompt,
    tip: { url: tip.url, git_sha: tip.git_sha, service: tip.service },
    conversation_url: conversationUrl,
    out_dir: path.relative(ROOT, outDir),
    frames: Object.fromEntries(
      Object.entries(frames).map(([k, v]) => [k, path.relative(ROOT, v)]),
    ),
    monologue_hits: monologueHits,
    monologue_clean: monologueHits.length === 0,
    v3,
    v3_human_page: !!(v3 && v3.human_page),
    missing_frames: missing,
    frames_complete: missing.length === 0,
    // #394: HTML scenes should open a real preview page (not chip-only V3).
    scene_visual_pass_eligible:
      missing.length === 0 &&
      monologueHits.length === 0 &&
      (args.skipProduct || !v3 || v3.opened === false || v3.human_page !== false),
    notes,
    wording: {
      if_pass: '场景视觉过（仍≠卡 Ready / ≠ CLAIM-WB）',
      if_fail: '产品未过 · REVISE',
      forbid: '禁止「单测绿故 Ready」/「无图全优 Ready」',
    },
  };

  fs.writeFileSync(path.join(outDir, 'manifest.json'), JSON.stringify(manifest, null, 2));
  fs.writeFileSync(
    path.join(outDir, 'README.md'),
    `# Visual gate · ${args.card} / ${args.scene}

\`\`\`text
BINDING #384 · 公网像人点完 · V0–V3 · 主气泡禁独白 · 无图不得 Ready
CLAIM-WB: NO · 本目录不蕴含产品 Ready
\`\`\`

| 项 | 值 |
|----|-----|
| tip | \`${tip.git_sha}\` |
| base | ${args.base} |
| conversation | ${conversationUrl || '—'} |
| frames complete | ${manifest.frames_complete ? 'Y' : 'N'} |
| monologue clean (heuristic) | ${manifest.monologue_clean ? 'Y' : 'N'} |
| scene visual pass eligible | ${manifest.scene_visual_pass_eligible ? 'Y' : 'N'} |

## Frames

| Frame | File |
|-------|------|
| V0 题面 | [V0-send.png](./V0-send.png) |
| V1 过程主气泡 | [V1-process-main.png](./V1-process-main.png) |
| V2 终态 | [V2-final.png](./V2-final.png) |
| V2 390 | [V2-final-390.png](./V2-final-390.png) |
| V3 产物打开 | [V3-open-product.png](./V3-open-product.png) |

审查必须 **读图**；只读本表 = 审查无效。

机器摘要：[manifest.json](./manifest.json)
`,
  );

  console.log(JSON.stringify(manifest, null, 2));
  if (missing.length || monologueHits.length) {
    process.exitCode = 1;
  }
}

run().catch((err) => {
  console.error(String(err && err.stack ? err.stack : err));
  process.exit(2);
});
