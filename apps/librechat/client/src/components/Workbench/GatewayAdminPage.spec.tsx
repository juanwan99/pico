import { render, screen, waitFor } from '@testing-library/react';
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
}));

import { picoAuthedGet } from '~/data-provider/pico/api';

describe('GatewayAdminPage', () => {
  beforeEach(() => {
    mockUser.role = 'ADMIN';
    (picoAuthedGet as jest.Mock).mockResolvedValue({
      ok: true,
      json: async () => ({
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
          needs_auth: true,
          tailnet_ui: 'https://aliyun-hy.tail217880.ts.net',
        },
        usage: { ok: true, billing: false, day: '2026-08-30', kinds: [], note: '老师用量。' },
      }),
    });
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
  });
});
