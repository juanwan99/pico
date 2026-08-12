import fs from 'fs';
import path from 'path';
import { expect, test } from '@playwright/test';

const outputDir = path.resolve(__dirname, '../../../../../docs/evidence/pack-ui-tasklist-fix');

const tasks = [
  {
    id: 'visual-failed',
    title: '请根据本学期全部课程数据生成一份非常详细的教学质量分析与改进方案',
    conversation_id: 'visual-conversation-failed',
    created_at: '2026-08-12T04:10:00Z',
    latest_run: {
      id: 'visual-run-failed',
      status: 'failed',
      user_message: '服务维护或重启导致任务中断，请打开后点「重新运行」。',
      ended_at: '2026-08-12T04:12:00Z',
    },
  },
  {
    id: 'visual-complete',
    title: '备课素材整理与课程大纲生成（含教学目标与课后练习）',
    conversation_id: 'visual-conversation-complete',
    created_at: '2026-08-12T03:00:00Z',
    latest_run: {
      id: 'visual-run-complete',
      status: 'succeeded',
      ended_at: '2026-08-12T03:08:00Z',
    },
  },
  {
    id: 'visual-running',
    title: '学生作业错因分析与分层训练建议',
    conversation_id: 'visual-conversation-running',
    created_at: '2026-08-12T02:00:00Z',
    latest_run: {
      id: 'visual-run-running',
      status: 'running',
      started_at: '2026-08-12T02:00:00Z',
    },
  },
];

async function mockTasks(page: import('@playwright/test').Page) {
  await page.route('**/api/pico/v1/tasks**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', json: { tasks } }),
  );
}

async function assertNoOverlap(
  first: import('@playwright/test').Locator,
  second: import('@playwright/test').Locator,
) {
  const [a, b] = await Promise.all([first.boundingBox(), second.boundingBox()]);
  expect(a).not.toBeNull();
  expect(b).not.toBeNull();
  if (!a || !b) {
    return;
  }
  const separated =
    a.x + a.width <= b.x || b.x + b.width <= a.x || a.y + a.height <= b.y || b.y + b.height <= a.y;
  expect(separated).toBe(true);
}

test('task history stays readable at narrow rail and 390 viewport', async ({ page }) => {
  fs.mkdirSync(outputDir, { recursive: true });
  await mockTasks(page);
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/c/new');

  const history = page.getByTestId('sidebar-task-history');
  await expect(history).toBeVisible();
  await expect(page.getByTestId('teacher-task-row')).toHaveCount(3);

  const failedRow = page.getByTestId('teacher-task-row').first();
  await assertNoOverlap(
    failedRow.getByTestId('teacher-task-title'),
    failedRow.getByTestId('teacher-task-status'),
  );
  await assertNoOverlap(
    failedRow.getByTestId('teacher-task-fail-hint'),
    failedRow.getByTestId('teacher-task-status'),
  );

  await page.screenshot({ path: path.join(outputDir, 'list-fail.png'), fullPage: true });
  await page
    .getByTestId('teacher-task-row')
    .nth(1)
    .screenshot({
      path: path.join(outputDir, 'list-ok.png'),
    });
  await page.locator('.pico-wb-sidebar').screenshot({
    path: path.join(outputDir, 'footer.png'),
  });

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  const expand = page.getByRole('button', { name: /展开侧栏|Open.*nav|menu/i }).first();
  if (await expand.isVisible().catch(() => false)) {
    await expand.click();
  }
  await expect(page.getByTestId('sidebar-task-history')).toBeVisible();
  await page.screenshot({ path: path.join(outputDir, 'v390.png'), fullPage: true });
});
