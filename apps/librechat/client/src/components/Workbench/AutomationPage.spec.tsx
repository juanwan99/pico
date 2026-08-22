import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import {
  createPicoAutomation,
  deletePicoAutomation,
  listPicoAutomations,
  listPicoRunEvents,
  runPicoAutomation,
  setPicoAutomationEnabled,
  type PicoAutomation,
} from '~/data-provider/pico/api';
import AutomationPage from './AutomationPage';

jest.mock('~/utils', () => ({
  cn: (...classes: unknown[]) =>
    classes
      .flatMap((value) => (typeof value === 'string' ? [value] : []))
      .filter(Boolean)
      .join(' '),
}));

jest.mock('~/data-provider/pico/api', () => ({
  createPicoAutomation: jest.fn(),
  deletePicoAutomation: jest.fn(),
  listPicoAutomations: jest.fn(),
  listPicoRunEvents: jest.fn(),
  runPicoAutomation: jest.fn(),
  setPicoAutomationEnabled: jest.fn(),
}));

const automation: PicoAutomation = {
  id: 'auto-1',
  name: '每日摘要',
  prompt: '【模型偏好：kimi-k2.6】\n汇总昨日动态',
  schedule_kind: 'periodic',
  schedule: {
    time: '09:00',
    model: 'kimi-k2.6',
    pico_ui: {
      schema: 'pico.automation-ui/v1',
      model: 'kimi-k2.6',
      workspace: { id: 'account-default', label: '账号默认工作空间' },
      permission: 'account-default',
      binding: { kind: 'none', id: 'none', label: '不绑定' },
      requested_enabled: true,
    },
  },
  enabled: true,
  last_run_at: null,
  next_run_at: '2026-07-31T01:00:00.000Z',
};

function renderPage(initialEntry = '/automation') {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <AutomationPage />
    </MemoryRouter>,
  );
}

describe('AutomationPage', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(listPicoAutomations).mockResolvedValue({ automations: [] });
    jest.mocked(createPicoAutomation).mockResolvedValue({ automation });
    jest.mocked(setPicoAutomationEnabled).mockResolvedValue({
      automation: { ...automation, enabled: false },
    });
    jest.mocked(runPicoAutomation).mockResolvedValue({
      automation: { ...automation, last_run_at: '2026-07-31T02:00:00.000Z' },
      task: {
        id: 'task-1',
        title: '[自动] 每日摘要',
        workspace_id: null,
      },
      run: {
        id: 'run-1',
        task_id: 'task-1',
        status: 'queued',
      },
    });
    jest.mocked(listPicoRunEvents).mockResolvedValue({ events: [] });
    jest.mocked(deletePicoAutomation).mockResolvedValue({ ok: true });
  });

  it('stores unsupported bindings as compatible schedule metadata and applies initial disabled state', async () => {
    renderPage();

    await screen.findByText('暂无自动化任务');
    fireEvent.click(screen.getAllByRole('button', { name: '添加任务' })[0]);

    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '研究周报' } });
    fireEvent.change(screen.getByLabelText('提示词'), {
      target: { value: '整理本周研究进展' },
    });
    fireEvent.change(screen.getByLabelText('模型偏好'), {
      target: { value: 'pico-agent' },
    });
    fireEvent.click(screen.getByRole('button', { name: /个人工作空间/ }));
    fireEvent.click(screen.getByRole('button', { name: /只读审阅/ }));
    fireEvent.change(screen.getByLabelText('绑定偏好'), {
      target: { value: 'expert-research' },
    });
    fireEvent.click(screen.getByRole('switch', { name: '创建后启用' }));
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => expect(createPicoAutomation).toHaveBeenCalledTimes(1));
    expect(createPicoAutomation).toHaveBeenCalledWith({
      name: '研究周报',
      prompt: '【模型偏好：pico-agent】\n整理本周研究进展',
      schedule_kind: 'periodic',
      schedule: {
        time: '09:00',
        model: 'pico-agent',
        pico_ui: {
          schema: 'pico.automation-ui/v1',
          model: 'pico-agent',
          workspace: { id: 'personal', label: '个人工作空间' },
          permission: 'read-only',
          binding: {
            kind: 'expert',
            id: 'expert-research',
            label: '专家 · 研究分析',
          },
          requested_enabled: false,
        },
      },
    });
    await waitFor(() => expect(setPicoAutomationEnabled).toHaveBeenCalledWith('auto-1', false));
  });

  it('binds an automation created from a project to that project workspace', async () => {
    renderPage('/automation?projectId=project-1&return=%2Fprojects%2Fproject-1');

    await screen.findByText('暂无自动化任务');
    expect(screen.getByRole('link', { name: '返回项目' })).toHaveAttribute(
      'href',
      '/projects/project-1',
    );
    fireEvent.click(screen.getAllByRole('button', { name: '添加任务' })[0]);
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: '项目周报' } });
    fireEvent.change(screen.getByLabelText('提示词'), {
      target: { value: '汇总项目进展并保存产物' },
    });
    fireEvent.click(screen.getByRole('button', { name: '保存' }));

    await waitFor(() => expect(createPicoAutomation).toHaveBeenCalledTimes(1));
    expect(createPicoAutomation).toHaveBeenCalledWith(
      expect.objectContaining({
        name: '项目周报',
        workspace_id: 'project-1',
        schedule: expect.objectContaining({
          pico_ui: expect.objectContaining({
            workspace: { id: 'project-1', label: '当前项目空间' },
          }),
        }),
      }),
    );
  });

  it('requires explicit confirmation before deleting an automation', async () => {
    jest.mocked(listPicoAutomations).mockResolvedValue({ automations: [automation] });
    renderPage();

    await screen.findByText('每日摘要');
    fireEvent.click(screen.getByRole('button', { name: '删除 每日摘要' }));

    expect(screen.getByRole('dialog', { name: '删除自动化任务？' })).toBeInTheDocument();
    expect(deletePicoAutomation).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => expect(deletePicoAutomation).toHaveBeenCalledWith('auto-1'));
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: '删除自动化任务？' })).not.toBeInTheDocument(),
    );
  });

  it('creates a real run from the run-once action and shows its status', async () => {
    jest.mocked(listPicoRunEvents).mockResolvedValue({
      events: [
        {
          id: 'event-1',
          run_id: 'run-1',
          seq: 1,
          type: 'tool.call',
          payload: { tool: 'calculator' },
        },
      ],
    });
    jest.mocked(listPicoAutomations).mockResolvedValue({ automations: [automation] });
    renderPage();

    await screen.findByText('每日摘要');
    fireEvent.click(screen.getByRole('button', { name: '运行一次 每日摘要' }));

    await waitFor(() => expect(runPicoAutomation).toHaveBeenCalledWith('auto-1'));
    expect(await screen.findByRole('status')).toHaveTextContent('已创建运行 · queued');
    expect(await screen.findByText('正在调工具')).toBeInTheDocument();
  });

  it('keeps run-once failures visible and recoverable', async () => {
    jest.mocked(listPicoAutomations).mockResolvedValue({ automations: [automation] });
    jest.mocked(runPicoAutomation).mockRejectedValue(new Error('502 unavailable'));
    renderPage();

    await screen.findByText('每日摘要');
    fireEvent.click(screen.getByRole('button', { name: '运行一次 每日摘要' }));

    expect(await screen.findByText('自动化服务暂时不可用，请稍后重试。')).toBeInTheDocument();
  });

  it('keeps the confirmation open and presents a recoverable delete error', async () => {
    jest.mocked(listPicoAutomations).mockResolvedValue({ automations: [automation] });
    jest.mocked(deletePicoAutomation).mockRejectedValue(new Error('502 unavailable'));
    renderPage();

    await screen.findByText('每日摘要');
    fireEvent.click(screen.getByRole('button', { name: '删除 每日摘要' }));
    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    const dialog = screen.getByRole('dialog', { name: '删除自动化任务？' });
    expect(
      await within(dialog).findByText('自动化服务暂时不可用，请稍后重试。'),
    ).toBeInTheDocument();
  });
});
