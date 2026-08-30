import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AccountsHubPage from './AccountsHubPage';

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

describe('AccountsHubPage', () => {
  it('opens Sub2API via the Pico HTTPS door and does not offer Pico CRUD', () => {
    render(
      <MemoryRouter>
        <AccountsHubPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole('heading', { name: '账号管理' })).toBeInTheDocument();
    const link = screen.getByTestId('open-sub2api-admin');
    expect(link).toHaveAttribute('href', 'https://pico.aivia.asia/accounts/enter-sub2api');
    expect(screen.getByTestId('exit-sub2api-admin')).toHaveAttribute(
      'href',
      'https://pico.aivia.asia/accounts/exit-sub2api',
    );
    expect(screen.queryByRole('form')).not.toBeInTheDocument();
    expect(screen.queryByText(/新建账号|删除账号|重置密码/)).not.toBeInTheDocument();
  });
});
