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
        new_api: { bind: '127.0.0.1:3000', role: 'reverse_proxy', ok: true, http: 200 },
        sub2api: { bind: '127.0.0.1:8081', role: 'account_polling_pool', ok: true, http: 200 },
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
      expect(screen.getByText('New API 反代')).toBeInTheDocument();
    });
    expect(screen.getByText('Sub2API 账号池')).toBeInTheDocument();
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
    expect(screen.getByText(/只给管理者/)).toBeInTheDocument();
    expect(picoAuthedGet).not.toHaveBeenCalled();
  });
});
