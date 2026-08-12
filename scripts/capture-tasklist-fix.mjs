#!/usr/bin/env node
import { createRequire } from "node:module";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const outDir = path.join(root, "docs/evidence/pack-ui-tasklist-fix");
const base = process.env.PICO_PUBLIC_BASE || "https://pico.aivia.asia";
const email = process.env.PICO_E2E_EMAIL || process.env.DEMO_EMAIL || "";
const password =
  process.env.PICO_E2E_PASSWORD || process.env.DEMO_PASSWORD || "";
const expectedSha = process.env.PICO_EXPECTED_SHA || "";

if (!email || password.length < 12 || !/^[0-9a-f]{40}$/.test(expectedSha)) {
  throw new Error(
    "BLOCKED: demo credentials and PICO_EXPECTED_SHA are required",
  );
}

fs.mkdirSync(outDir, { recursive: true });

async function noOverlap(first, second) {
  const [a, b] = await Promise.all([first.boundingBox(), second.boundingBox()]);
  if (!a || !b) return false;
  return (
    a.x + a.width <= b.x ||
    b.x + b.width <= a.x ||
    a.y + a.height <= b.y ||
    b.y + b.height <= a.y
  );
}

const tip = await (
  await fetch(`${base}/api/pico/tip?cb=${expectedSha}`)
).json();
if (tip.git_sha !== expectedSha) {
  throw new Error(`tip mismatch: ${tip.git_sha}`);
}

const browser = await chromium.launch({
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  locale: "zh-CN",
});
const page = await context.newPage();

try {
  await page.goto(`${base}/login`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page
    .locator('input[type="email"], input[name="email"]')
    .first()
    .fill(email);
  await page.locator('input[type="password"]').first().fill(password);
  await page
    .locator('button[type="submit"], [data-testid="login-button"]')
    .first()
    .click();
  await page.waitForURL((url) => !url.pathname.includes("/login"), {
    timeout: 45000,
  });
  await page.goto(`${base}/c/new?cb=${expectedSha}`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(4000);

  const sidebar = page.locator(".pico-wb-sidebar").first();
  const rows = page.locator('[data-testid="teacher-task-row"]');
  await sidebar.waitFor({ state: "visible", timeout: 30000 });

  const rowCount = await rows.count();
  const rowChecks = [];
  for (let i = 0; i < rowCount; i++) {
    const row = rows.nth(i);
    const title = row.locator('[data-testid="teacher-task-title"]');
    const status = row.locator('[data-testid="teacher-task-status"]');
    const hint = row.locator('[data-testid="teacher-task-fail-hint"]');
    rowChecks.push({
      title_status_no_overlap: await noOverlap(title, status),
      hint_status_no_overlap: (await hint.count())
        ? await noOverlap(hint, status)
        : true,
    });
  }

  await page.screenshot({
    path: path.join(outDir, "list-fail.png"),
    fullPage: true,
  });
  await sidebar.screenshot({ path: path.join(outDir, "footer.png") });
  const completedRows = rows.filter({ hasText: "已完成" });
  const completedRowCount = await completedRows.count();
  const firstTaskHref =
    rowCount > 0 ? await rows.first().getAttribute("href") : null;
  if (completedRowCount > 0) {
    await completedRows.first().scrollIntoViewIfNeeded();
    await sidebar.screenshot({ path: path.join(outDir, "list-ok.png") });
  }

  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${base}${firstTaskHref || "/c/new"}?cb=${expectedSha}-390`, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(1000);
  const expand = page.getByTestId("open-sidebar-button").first();
  await expand.waitFor({ state: "visible", timeout: 30000 });
  await expand.click();
  await page.waitForTimeout(600);
  await page
    .locator('#chat-history-nav, [data-testid="mobile-nav"], .pico-wb-sidebar')
    .first()
    .screenshot({ path: path.join(outDir, "v390.png") });

  const report = {
    tip,
    row_count: rowCount,
    completed_row_count: completedRowCount,
    list_ok_size_bytes: fs.statSync(path.join(outDir, "list-ok.png")).size,
    row_checks: rowChecks,
    overlap_pass: rowChecks.every(
      (row) => row.title_status_no_overlap && row.hint_status_no_overlap,
    ),
    claim_wb: "NO",
  };
  fs.writeFileSync(
    path.join(outDir, "manifest.json"),
    JSON.stringify(report, null, 2),
  );
  console.log(JSON.stringify(report, null, 2));
  if (!report.overlap_pass) process.exitCode = 3;
} finally {
  await browser.close();
}
