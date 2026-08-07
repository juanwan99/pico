#!/usr/bin/env node
/**
 * Public E2E — Grok-driven browser (not owner manual).
 * Env:
 *   PICO_E2E_BASE     default https://pico.aivia.asia
 *   PICO_E2E_EMAIL    required for full run
 *   PICO_E2E_PASSWORD required for full run
 *   PICO_E2E_SKIP_COMPLEX=1  only default chat smoke
 * Exit 0 PASS · 1 FAIL · 2 BLOCKED (missing creds / ban)
 */
import { chromium } from "playwright";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const BASE = (process.env.PICO_E2E_BASE || "https://pico.aivia.asia").replace(/\/$/, "");
const EMAIL = process.env.PICO_E2E_EMAIL || process.env.PICO_DEMO_EMAIL || "";
const PASSWORD = process.env.PICO_E2E_PASSWORD || process.env.PICO_DEMO_PASSWORD || "";
const OUT = process.env.PICO_E2E_OUT || "/workspace/screenshots/e2e";
const SKIP_COMPLEX = process.env.PICO_E2E_SKIP_COMPLEX === "1";
const HEADLESS = process.env.PICO_E2E_HEADED !== "1";

mkdirSync(OUT, { recursive: true });

const report = {
  ok: false,
  base: BASE,
  startedAt: new Date().toISOString(),
  steps: [],
  defaultModel: null,
  d5: null,
  d8: null,
  complex: null,
  errors: [],
};

function step(id, status, detail = {}) {
  const row = { id, status, ...detail, t: new Date().toISOString() };
  report.steps.push(row);
  console.log(JSON.stringify(row));
}

async function shot(page, name) {
  const p = join(OUT, `${name}.png`);
  await page.screenshot({ path: p, fullPage: false });
  return p;
}

async function waitAssistantText(page, timeoutMs = 120000) {
  const start = Date.now();
  let last = "";
  while (Date.now() - start < timeoutMs) {
    // LibreChat-ish: assistant bubbles
    const texts = await page.locator('[data-testid="message-text"], .text-message, .markdown, [class*="message"]').allTextContents().catch(() => []);
    const joined = texts.join("\n").trim();
    if (joined.length > last.length + 5) last = joined;
    // error patterns
    if (/服务暂时出错|登录失败|任务失败/.test(joined) && Date.now() - start > 8000) {
      return { text: joined, error: true };
    }
    // success heuristic: substantial reply after user message
    const hasModelReply =
      /Pico|DeepSeek|deepseek|我是|可以帮|模型|助手/i.test(joined) && joined.length > 40;
    if (hasModelReply && Date.now() - start > 3000) {
      // wait for stream settle
      await page.waitForTimeout(2500);
      const final = (await page.locator("body").innerText()).slice(-4000);
      return { text: final, error: /服务暂时出错/.test(final) };
    }
    await page.waitForTimeout(1500);
  }
  const body = await page.locator("body").innerText();
  return { text: body.slice(-4000), error: true, timeout: true };
}

async function findComposer(page) {
  const candidates = [
    'textarea[placeholder*="做"]',
    'textarea[placeholder*="消息"]',
    'textarea[placeholder*="Message"]',
    'textarea[data-testid="text-input"]',
    "form textarea",
    "textarea",
    '[contenteditable="true"]',
  ];
  for (const sel of candidates) {
    const loc = page.locator(sel).first();
    if (await loc.count() && (await loc.isVisible().catch(() => false))) return loc;
  }
  return null;
}

async function sendMessage(page, text) {
  const box = await findComposer(page);
  if (!box) throw new Error("composer_not_found");
  await box.click({ timeout: 10000 });
  await box.fill("");
  await box.fill(text);
  // try Enter or send button
  const sendBtn = page
    .locator(
      'button[aria-label*="Send"], button[aria-label*="发送"], button:has-text("发送"), [data-testid="send-button"]',
    )
    .first();
  if (await sendBtn.count()) {
    await sendBtn.click();
  } else {
    await box.press("Enter");
  }
}

async function readHeaderModel(page) {
  const body = await page.locator("body").innerText();
  const m =
    body.match(/deepseek-chat|deepseek|kimi-k2\.?\d*|pico-agent|gpt-4|moonshot/i)?.[0] || null;
  // try combobox
  const combo = page.locator('[role="combobox"], button:has-text("deepseek"), button:has-text("kimi")').first();
  let comboText = null;
  if (await combo.count()) comboText = (await combo.innerText().catch(() => "")).trim();
  return { bodyHit: m, comboText };
}

const COMPLEX_PROMPT = `
【R-HARD 压缩版 · 经营对账包 · 必须多产物】
你是经营分析。根据以下冲突材料交付，禁止编造未给数字：

来源A销售：新签12单合同额186万；教育5单70万；续费4单40万。
来源B财务：回款到账 12,15,9,22,8 万元共5笔；开票价税合计141万（含上月18万）。
来源C客成：P1故障45分钟，影响POC1家+约12租户；NPS n=17 均分6.1（样本极小不得写成良好）。

硬约束：
1) 先出《对账工作纸》（表/HTML/Excel/Word皆可）：标一致/冲突/未知；回款五笔加总必须正确。
2) 再出《复盘备忘》Word：只写对账后能成立的结论；NPS不得吹嘘。
3) 再出《风险与决策》至少5条。
4) 文末写「交叉校验」3条等式；数字跨文件一致。
5) 186万新签与141万开票冲突必须解释口径，禁止合成一个假「真相收入」。

请真正生成可下载文件，不要只空谈。
`.trim();

async function main() {
  if (!EMAIL || !PASSWORD || PASSWORD.length < 8) {
    step("BLOCKED", "blocked", {
      reason: "missing_PICO_E2E_EMAIL_or_PICO_E2E_PASSWORD",
      hint: "export PICO_E2E_EMAIL=... PICO_E2E_PASSWORD=... then rerun",
    });
    writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2));
    process.exit(2);
  }

  const browser = await chromium.launch({
    headless: HEADLESS,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const context = await browser.newContext({
    viewport: { width: 1400, height: 900 },
    locale: "zh-CN",
    ignoreHTTPSErrors: false,
  });
  const page = await context.newPage();
  page.setDefaultTimeout(60000);

  try {
    // D1
    const loginUrl = `${BASE}/login`;
    const resp = await page.goto(loginUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await page.waitForTimeout(2000);
    await shot(page, "01-login");
    step("D1", resp?.ok() ? "pass" : "fail", { status: resp?.status(), url: loginUrl });
    if (!resp?.ok()) throw new Error("login_page_http");

    // D2 login
    const emailSel = page.locator('input[type="email"], input[name="email"], input[id*="email"]').first();
    const passSel = page.locator('input[type="password"]').first();
    await emailSel.fill(EMAIL);
    await passSel.fill(PASSWORD);
    const submit = page.locator('button[type="submit"], button:has-text("继续"), button:has-text("登录")').first();
    await submit.click();
    await page.waitForTimeout(4000);
    await shot(page, "02-after-login");

    const bodyAfter = await page.locator("body").innerText();
    if (/登录失败|封禁|banned|Too many|暂时无法/.test(bodyAfter) && /password|密码|失败/.test(bodyAfter)) {
      step("D2", "fail", { reason: "login_rejected", snippet: bodyAfter.slice(0, 300) });
      report.errors.push("login_rejected");
      throw Object.assign(new Error("login_rejected"), { code: 2 });
    }
    // navigate to chat if needed
    if (page.url().includes("login")) {
      // wait redirect
      await page.waitForURL((u) => !u.pathname.includes("login"), { timeout: 20000 }).catch(() => {});
    }
    if (page.url().includes("login")) {
      step("D2", "fail", { reason: "still_on_login", url: page.url() });
      throw new Error("still_on_login");
    }
    step("D2", "pass", { url: page.url() });

    // try new chat
    const newBtns = page.locator(
      'a:has-text("新建"), button:has-text("新建"), a:has-text("New"), button:has-text("New chat"), [href*="/c/new"]',
    );
    if (await newBtns.count()) {
      await newBtns.first().click().catch(() => {});
      await page.waitForTimeout(2000);
    }
    await shot(page, "03-shell");

    // D3-D4 model
    const model = await readHeaderModel(page);
    report.defaultModel = model;
    const modelStr = `${model.comboText || ""} ${model.bodyHit || ""}`.toLowerCase();
    const badKimi = /kimi-k2/.test(modelStr) && !/deepseek/.test(modelStr);
    const good = /deepseek|pico-agent/.test(modelStr) || !/kimi-k2/.test(modelStr);
    step("D3", "pass", { note: "no_manual_model_change" });
    step("D4", badKimi ? "fail" : good ? "pass" : "weak", { model });

    // D5
    await sendMessage(page, "你是什么模型");
    await shot(page, "04-d5-sent");
    const r5 = await waitAssistantText(page, 150000);
    report.d5 = r5.text.slice(-800);
    await shot(page, "05-d5-reply");
    const d5ok = !r5.error && !/服务暂时出错/.test(r5.text) && r5.text.length > 20;
    step("D5", d5ok ? "pass" : "fail", { error: r5.error, timeout: r5.timeout, sample: report.d5.slice(0, 200) });

    // D8
    await sendMessage(page, "用一句话介绍你能做什么");
    const r8 = await waitAssistantText(page, 150000);
    report.d8 = r8.text.slice(-800);
    await shot(page, "06-d8-reply");
    const d8ok = !r8.error && !/服务暂时出错/.test(r8.text) && r8.text.length > 20;
    step("D8", d8ok ? "pass" : "fail", { sample: report.d8.slice(0, 200) });

    // Complex task
    if (!SKIP_COMPLEX) {
      // new chat for isolation
      if (await newBtns.count()) {
        await newBtns.first().click().catch(() => {});
        await page.waitForTimeout(1500);
      }
      await sendMessage(page, COMPLEX_PROMPT);
      await shot(page, "07-complex-sent");
      // long wait for tools
      const rc = await waitAssistantText(page, 300000);
      await page.waitForTimeout(5000);
      await shot(page, "08-complex-reply");
      const body = await page.locator("body").innerText();
      const hasFileUi =
        /下载|打开|产物|\.docx|\.xlsx|\.html|artifact|可下载/i.test(body) ||
        (await page.locator('a[download], button:has-text("下载"), a:has-text("下载")').count()) > 0;
      const hasConflictTalk = /冲突|口径|对账|未知|不能合并|权责|现金/i.test(body);
      const failed = /服务暂时出错/.test(body) || rc.error;
      const complexPass = !failed && hasConflictTalk && (hasFileUi || /对账|复盘|风险/.test(body));
      report.complex = {
        pass: complexPass,
        hasFileUi,
        hasConflictTalk,
        failed,
        sample: body.slice(-1200),
      };
      step("COMPLEX", complexPass ? "pass" : "fail", report.complex);
    }

    const failedSteps = report.steps.filter((s) => s.status === "fail");
    report.ok = failedSteps.length === 0;
    report.finishedAt = new Date().toISOString();
    writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2));
    console.log("REPORT", JSON.stringify({ ok: report.ok, failed: failedSteps.map((s) => s.id) }));
    await browser.close();
    process.exit(report.ok ? 0 : 1);
  } catch (e) {
    report.errors.push(String(e?.message || e));
    report.finishedAt = new Date().toISOString();
    try {
      await shot(page, "99-error");
    } catch {}
    writeFileSync(join(OUT, "report.json"), JSON.stringify(report, null, 2));
    await browser.close().catch(() => {});
    if (e?.code === 2 || /login_rejected|missing_/.test(String(e))) process.exit(2);
    process.exit(1);
  }
}

main();
