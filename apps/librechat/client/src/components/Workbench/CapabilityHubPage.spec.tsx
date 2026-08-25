import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import CapabilityHubPage from './CapabilityHubPage';

const mockToggle = jest.fn();

jest.mock('~/utils', () => ({
  cn: (...classes: unknown[]) =>
    classes
      .flatMap((value) => (typeof value === 'string' ? [value] : []))
      .filter(Boolean)
      .join(' '),
}));

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

jest.mock('~/data-provider', () => ({
  useListSkillsQuery: () => ({
    data: {
      skills: [
        {
          _id: 'skill-chat',
          name: 'skill.chat',
          displayTitle: '闲聊',
          description: '纯对话',
          author: 'user-1',
          source: 'inline',
        },
        {
          _id: 'skill-off',
          name: 'skill.off',
          displayTitle: '已关技能',
          description: '默认关',
          author: 'user-2',
          source: 'inline',
        },
      ],
    },
    isLoading: false,
    isError: false,
  }),
}));

jest.mock('~/hooks', () => ({
  useSkillActiveState: () => ({
    isActive: (skill: { _id: string }) => skill._id !== 'skill-off',
    toggle: mockToggle,
    isLoading: false,
  }),
}));

function renderPage(entry = '/capability') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <CapabilityHubPage />
    </MemoryRouter>,
  );
}

describe('CapabilityHubPage', () => {
  beforeEach(() => {
    mockToggle.mockClear();
  });

  it('shows skills and connectors tabs, not experts or empty shells', () => {
    renderPage();

    expect(screen.getByRole('heading', { name: '技能与连接器' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '技能' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: '连接器' })).toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: '专家' })).not.toBeInTheDocument();
    expect(screen.getByText('闲聊')).toBeInTheDocument();
    expect(screen.getByRole('switch', { name: '闲聊 已开启' })).toHaveAttribute(
      'aria-checked',
      'true',
    );
    expect(screen.getByRole('switch', { name: '已关技能 已关闭' })).toHaveAttribute(
      'aria-checked',
      'false',
    );
  });

  it('toggles a skill instead of starting a new task', () => {
    renderPage();
    fireEvent.click(screen.getByRole('switch', { name: '闲聊 已开启' }));
    expect(mockToggle).toHaveBeenCalledTimes(1);
    expect(screen.queryByText('用此技能新建任务')).not.toBeInTheDocument();
  });

  it('lists only school knowledge base and MCP on the connectors tab', () => {
    renderPage('/capability?tab=connectors');

    expect(screen.getByText('学校知识库')).toBeInTheDocument();
    expect(screen.getByText('已接通')).toBeInTheDocument();
    expect(screen.getByText('MCP')).toBeInTheDocument();
    expect(screen.getByText('未接')).toBeInTheDocument();
    expect(screen.queryByText('邮箱')).not.toBeInTheDocument();
    expect(screen.queryByText('腾讯文档')).not.toBeInTheDocument();
  });
});
