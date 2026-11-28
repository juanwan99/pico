import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import GatewayAdminPage from './GatewayAdminPage';

const mockUser = { role: 'ADMIN' as string };

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: () => <span />,
}));

jest.mock('./WorkbenchShell', () => ({
  __esModule: true,
  default: ({ children, title }: { children: React.ReactNode; title: string }) => (
    <main>
      <h1>{title}</h1>
      {children}
    </main>
  ),
}));

jest.mock('~/hooks/AuthContext', () => ({
  useAuthContext: () => ({ user: mockUser }),
}));

jest.mock('~/data-provider/pico/api', () => ({
  picoAuthedGet: jest.fn(),
  picoAuthedPost: jest.fn(),
}));

import { picoAuthedGet, picoAuthedPost } from '~/data-provider/pico/api';

const baseStatus = {
  ok: true,
  sub2api_is_frontend: false,
  pico_talks_to: 'new_api',
  brain: { via: 'new_api', model: 'gpt-5.6-sol' },
  new_api: { bind: '0.0.0.0:3000', role: 'pipe', ok: true, http: 200, models: ['gpt-5.6-sol'] },
  sub2api: {
    bind: '127.0.0.1:8081',
    role: 'account_login_state',
    ok: true,
    http: 200,
    needs_auth: false,
    compliance_required: false,
    monitor_count: 0,
    monitors: [] as unknown[],
    accounts: [] as unknown[],
    account_ui: 'https://workbench.aivia.asia',
    tailnet_ui: 'https://workbench.aivia.asia',
  },
  usage: { ok: true, billing: false, day: '2026-08-30', kinds: [], note: '老师用量。' },
};

function jsonOk(body: unknown) {
  return { ok: true, json: async () => body };
}

describe('GatewayAdminPage', () => {
  beforeEach(() => {
    mockUser.role = 'ADMIN';
    (picoAuthedGet as jest.Mock).mockResolvedValue(jsonOk(baseStatus));
    (picoAuthedPost as jest.Mock).mockResolvedValue(jsonOk({ ok: true, message: '已交给上游。' }));
  });

  it('shows manager probes and does not open Sub2API as a frontend', async () => {
    render(
      <MemoryRouter>
        <GatewayAdminPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('heading', { name: '网关管理' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/打开账号台/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /打开账号台/ })).toHaveAttribute(
        'href',
        'https://workbench.aivia.asia',
      );
    });
    expect(screen.getByText('管道 · New API')).toBeInTheDocument();
    expect(screen.getByText('账号 · Sub2API 登录态')).toBeInTheDocument();
    expect(screen.getByText('用户消耗 · Pico usage_events')).toBeInTheDocument();
    expect(screen.getByText(/聊天脑已走 New API/)).toBeInTheDocument();
    expect(screen.getByText(/还没有渠道监控记录/)).toBeInTheDocument();
    expect(screen.getByText(/还没有订阅号/)).toBeInTheDocument();
    expect(screen.queryByTestId('open-sub2api-admin')).not.toBeInTheDocument();
    expect(screen.queryByText(/打开账号管理/)).not.toBeInTheDocument();
  });

  it('hides both tables on role change and never fetches for a teacher', async () => {
    mockUser.role = 'USER';
    const { rerender } = render(<GatewayAdminPage />);
    expect(screen.getByText(/只给所有者/)).toBeInTheDocument();
    expect(picoAuthedGet).not.toHaveBeenCalled();

    mockUser.role = 'ADMIN';
    rerender(<GatewayAdminPage />);
    await screen.findByRole('link', { name: /打开账号台/ });
    expect(screen.getAllByRole('table')).toHaveLength(2);
    mockUser.role = 'USER';
    rerender(<GatewayAdminPage />);
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(picoAuthedGet).toHaveBeenCalledTimes(1);
    expect(picoAuthedPost).not.toHaveBeenCalled();
  });

  it('paints 7-day availability and 168h bars, and filters by bucket', async () => {
    const timeline = Array.from({ length: 168 }, (_, i) => ({
      status: i < 160 ? 'operational' : 'failed',
      bucket: i < 160 ? '健康' : '严重',
      checked_at: `2026-08-2${String(i % 10)}T00:00:00Z`,
    }));
    (picoAuthedGet as jest.Mock).mockResolvedValue(
      jsonOk({
        ...baseStatus,
        sub2api: {
          ...baseStatus.sub2api,
          monitor_count: 2,
          monitors: [
            {
              id: 1,
              name: 'Gemini A',
              provider: 'google',
              bucket: '健康',
              availability_7d: 0.992,
              primary_latency_ms: 120,
              timeline,
            },
            {
              id: 2,
              name: 'Grok B',
              provider: 'xai',
              bucket: '严重',
              availability_7d: 0.41,
              timeline: [{ status: 'failed', bucket: '严重' }],
            },
          ],
        },
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GatewayAdminPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Gemini A')).toBeInTheDocument();
    });
    expect(screen.getByText('99.2%')).toBeInTheDocument();
    expect(screen.getByLabelText('近 168 小时')).toBeInTheDocument();
    expect(screen.getByText('Grok B')).toBeInTheDocument();
    expect(screen.getByText('120 ms')).toBeInTheDocument();
    const section = within(screen.getByRole('region', { name: '服务状态 · 近 7 天' }));
    await user.click(section.getByRole('button', { name: '筛选' }));
    await user.click(screen.getByRole('checkbox', { name: '严重' }));
    expect(screen.getByText('Grok B')).toBeInTheDocument();
    expect(screen.queryByText('Gemini A')).not.toBeInTheDocument();
  });

  it('posts refresh and shows a 423 compliance line without fake success', async () => {
    (picoAuthedGet as jest.Mock).mockResolvedValue(
      jsonOk({
        ...baseStatus,
        sub2api: {
          ...baseStatus.sub2api,
          accounts: [
            {
              id: 9,
              name: '订阅号甲',
              platform: 'google',
              status: 'error',
              error: 'token stale',
              soft_actions: ['refresh', 'test', 'clear-error', 'recover-state'],
            },
          ],
        },
      }),
    );
    (picoAuthedPost as jest.Mock).mockResolvedValue({
      ok: false,
      status: 423,
      json: async () => ({
        ok: false,
        http: 423,
        message: '要先在账号台签合规承诺。Pico 不代签。',
      }),
    });
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <GatewayAdminPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('订阅号甲')).toBeInTheDocument();
    });
    await user.click(screen.getByRole('button', { name: '刷新' }));
    expect(picoAuthedPost).toHaveBeenCalledWith('/api/pico/v1/admin/gateway/accounts/9/refresh');
    await waitFor(() => {
      expect(screen.getByText(/Pico 不代签/)).toBeInTheDocument();
    });
    expect(screen.queryByText('已交给上游。')).not.toBeInTheDocument();
  });
  it('retains subscription filters and sorting after refresh replaces all rows', async () => {
    const accounts = [
      { id: 9, name: 'Bravo', platform: 'google', status: 'error', schedulable: false },
      { id: 10, name: 'Alpha', platform: 'google', status: 'ok', schedulable: true },
      { id: 11, name: 'Other', platform: 'openai', status: 'ok', schedulable: true },
    ];
    const status = (rows: typeof accounts) =>
      jsonOk({ ...baseStatus, sub2api: { ...baseStatus.sub2api, accounts: rows } });
    jest.mocked(picoAuthedGet)
      .mockResolvedValueOnce(status(accounts) as Response)
      .mockResolvedValueOnce(status([{ ...accounts[0], name: 'Charlie' }, ...accounts.slice(1)]) as Response);
    const user = userEvent.setup();
    render(<GatewayAdminPage />);
    await screen.findByText('Bravo');
    const section = within(screen.getByRole('region', { name: '订阅号登录态' }));
    await user.click(section.getByRole('button', { name: /^订阅号 column/ }));
    await user.click(section.getByRole('button', { name: '筛选' }));
    await user.click(screen.getByRole('checkbox', { name: 'google' }));
    await user.keyboard('{Escape}');
    await user.click(within(section.getByRole('row', { name: /Bravo/ })).getByRole('button', { name: '刷新' }));
    await screen.findByText('Charlie');
    expect(section.getAllByRole('rowheader').map((cell) => cell.textContent)).toEqual(['Alpha', 'Charlie']);
    expect(section.getByRole('button', { name: '平台：google ×' })).toBeInTheDocument();
  });

});
