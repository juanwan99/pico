import { render, screen, waitFor } from '@testing-library/react';
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
    tailnet_ui: 'https://aliyun-hy.tail217880.ts.net',
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
      expect(screen.getByText(/打开尾网账号台/)).toBeInTheDocument();
    });
    expect(screen.getByText('管道 · New API')).toBeInTheDocument();
    expect(screen.getByText('账号 · Sub2API 登录态')).toBeInTheDocument();
    expect(screen.getByText('用户消耗 · Pico usage_events')).toBeInTheDocument();
    expect(screen.getByText(/聊天脑已走 New API/)).toBeInTheDocument();
    expect(screen.getByText(/还没有监控卡/)).toBeInTheDocument();
    expect(screen.queryByTestId('open-sub2api-admin')).not.toBeInTheDocument();
    expect(screen.queryByText(/打开账号管理/)).not.toBeInTheDocument();
  });

  it('hides probes from teacher accounts', () => {
    mockUser.role = 'USER';
    render(
      <MemoryRouter>
        <GatewayAdminPage />
      </MemoryRouter>,
    );
    expect(screen.getByText(/只给所有者/)).toBeInTheDocument();
    expect(picoAuthedGet).not.toHaveBeenCalled();
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
    await user.click(screen.getByRole('tab', { name: /严重/ }));
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
        message: '要先在尾网 Sub2API 真页签合规承诺。Pico 不代签。',
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
});
