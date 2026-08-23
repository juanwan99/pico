import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { listPicoSkillCatalog, type PicoSkillPolicy } from '~/data-provider/pico/api';
import CapabilityHubPage from './CapabilityHubPage';

jest.mock('~/utils', () => ({
  cn: (...classes: unknown[]) =>
    classes
      .flatMap((value) => (typeof value === 'string' ? [value] : []))
      .filter(Boolean)
      .join(' '),
}));

jest.mock('~/utils/picoModelPref', () => ({
  preferredModelForExpert: jest.fn(() => 'pico-agent'),
  preferredModelForSkill: jest.fn(() => 'pico-agent'),
  setActiveExpert: jest.fn(),
  setPicoModelMode: jest.fn(),
  queuePendingModel: jest.fn(),
}));

jest.mock('~/data-provider/pico/api', () => ({
  listPicoSkillCatalog: jest.fn(),
}));

jest.mock('./WorkbenchShell', () => ({
  __esModule: true,
  default: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));

const skills: PicoSkillPolicy[] = [
  {
    id: 'skill-chat',
    name: 'skill.chat',
    tools: [],
    risk: 'low',
    requires_s7: false,
  },
  {
    id: 'skill-summarize',
    name: 'skill.summarize',
    tools: ['workspace_read_file', 'structured_outline', 'workspace_write_file'],
    risk: 'low',
    requires_s7: false,
  },
  {
    id: 'skill-write-s7',
    name: 'skill.write_s7',
    tools: ['pico_propose_change'],
    risk: 'write_s7',
    requires_s7: true,
  },
  {
    id: 'skill-unknown',
    name: 'skill.unknown',
    tools: ['unsafe_all_tools'],
    risk: 'unknown',
    requires_s7: false,
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/capability?tab=skills']}>
      <CapabilityHubPage />
    </MemoryRouter>,
  );
}

describe('CapabilityHubPage skill policies', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    jest.mocked(listPicoSkillCatalog).mockResolvedValue({ skills });
  });

  it('renders policy-bound tools and keeps unknown skills fail-closed', async () => {
    renderPage();

    const summarize = await screen.findByRole('button', { name: /skill\.summarize/i });
    expect(summarize).toHaveTextContent('workspace_read_file');
    expect(summarize).toHaveTextContent('structured_outline');

    const chat = screen.getByRole('button', { name: /skill\.chat/i });
    expect(chat).toHaveTextContent('工具：无工具');
    expect(chat).toHaveTextContent('风险：纯对话');
    expect(screen.queryByText('skill.unknown')).not.toBeInTheDocument();
    expect(screen.queryByText('unsafe_all_tools')).not.toBeInTheDocument();
  });

  it('shows write_s7 proposal tooling with the confirmation requirement', async () => {
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /skill\.write_s7/i }));

    const policy = screen.getByText('工具权限（只读）').parentElement?.parentElement;
    expect(policy).toBeTruthy();
    expect(within(policy as HTMLElement).getByText('pico_propose_change')).toBeInTheDocument();
    expect(within(policy as HTMLElement).getByText('写入提案 · 需确认')).toBeInTheDocument();
    expect(
      within(policy as HTMLElement).getByText('仅生成变更提案，必须经人工确认后执行。'),
    ).toBeInTheDocument();
  });
});
