import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import Landing from '../Landing';

jest.mock(
  'librechat-data-provider',
  () => ({
    apiBaseUrl: () => '',
    EModelEndpoint: { azureOpenAI: 'azureOpenAI', openAI: 'openAI' },
  }),
  { virtual: true },
);

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

jest.mock('~/hooks/Messages/useSubmitMessage', () => ({
  __esModule: true,
  default: () => ({ submitMessage: jest.fn() }),
}));

jest.mock('~/hooks', () => ({
  useAuthContext: () => ({ user: { name: '老师' } }),
  useFileHandlingNoChatContext: () => ({ handleFileChange: jest.fn() }),
}));

jest.mock('~/Providers', () => ({
  useOptionalChatFormContext: () => ({
    setValue: jest.fn(),
  }),
  useOptionalChatContext: () => ({
    setConversation: jest.fn(),
  }),
}));

jest.mock('~/components/Chat/Input/WorkspaceSelector', () => ({
  __esModule: true,
  default: () => <div data-testid="workspace-selector">工作空间</div>,
}));

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: () => <span data-testid="pico-icon" />,
}));

jest.mock('~/utils/picoModelPref', () => ({
  consumePendingModel: () => null,
  getPicoModelMode: () => 'pico-fast',
  labelForPicoModel: (id: string) => id,
  normalizePicoModelMode: (id: string) => id,
  PICO_DUAL_MODELS: [{ id: 'pico-fast', label: '快速' }],
  setPicoModelMode: jest.fn(),
}));

describe('Landing composer chrome', () => {
  it('U1: idle composer is one input + plus, no 调用技能与指令 second layer', () => {
    render(<Landing centerFormOnLanding />);
    const input = screen.getByTestId('text-input');
    expect(input).toHaveAttribute('placeholder', '发消息');
    expect(screen.getByTestId('composer-plus')).toBeInTheDocument();
    expect(screen.queryByText(/调用技能与指令/)).not.toBeInTheDocument();
    expect(screen.queryByText('默认权限')).not.toBeInTheDocument();
    expect(screen.queryByText('工作空间')).not.toBeInTheDocument();
    expect(screen.queryByText('日常办公')).not.toBeInTheDocument();
    expect(screen.queryByTestId('composer-plus-menu')).not.toBeInTheDocument();
  });

  it('C1: plus, input, and send sit on one row', () => {
    render(<Landing centerFormOnLanding />);
    const row = screen.getByTestId('composer-one-row');
    expect(row).toContainElement(screen.getByTestId('composer-plus'));
    expect(row).toContainElement(screen.getByTestId('text-input'));
    expect(row).toContainElement(screen.getByTestId('send-button'));
    expect(screen.getByTestId('composer-plus').textContent?.trim()).not.toBe('+');
  });

  it('plus menu is 快速 / 深度 / 上传附件 only', () => {
    render(<Landing centerFormOnLanding />);
    fireEvent.click(screen.getByTestId('composer-plus'));
    expect(screen.getByTestId('composer-plus-menu')).toBeInTheDocument();
    expect(screen.getByTestId('composer-plus-mode-pico-fast')).toHaveTextContent('快速');
    expect(screen.getByTestId('composer-plus-mode-pico-deep')).toHaveTextContent('深度');
    expect(screen.getByTestId('composer-plus-attach')).toHaveTextContent('上传附件');
    expect(screen.queryByText('默认权限')).not.toBeInTheDocument();
    expect(screen.queryByText(/工作空间/)).not.toBeInTheDocument();
  });
});
