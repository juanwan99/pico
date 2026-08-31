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

jest.mock('~/components/Chat/Input/Files/FileFormChat', () => ({
  __esModule: true,
  default: () => <div data-testid="file-form-chat" />,
}));

jest.mock('~/components/Chat/SchoolMaterialsBar', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('~/components/Chat/ArchiveFolderBar', () => ({
  __esModule: true,
  default: () => null,
}));

jest.mock('~/components/Chat/PointsBar', () => ({
  __esModule: true,
  default: () => null,
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
  getPicoPlanOn: () => false,
  labelForPicoModel: (id: string) => id,
  normalizePicoModelMode: (id: string) => id,
  PICO_DUAL_MODELS: [{ id: 'pico-fast', label: '快速' }],
  patchConversationModel: (prev: { model?: string } | null, id: string) =>
    prev ? { ...prev, model: id } : prev,
  patchConversationPlan: (prev: { pico_plan?: boolean } | null, on: boolean) =>
    prev ? { ...prev, pico_plan: on } : prev,
  setPicoModelMode: jest.fn(),
  setPicoPlanOn: jest.fn(),
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
    expect(row).toContainElement(screen.getByTestId('composer-mode-switch'));
    expect(row).toContainElement(screen.getByTestId('composer-plan-toggle'));
    expect(screen.getByTestId('composer-plus').textContent?.trim()).not.toBe('+');
  });

  it('plus opens the file picker; 快速/深度 sit as a switch', () => {
    render(<Landing centerFormOnLanding />);
    expect(screen.queryByTestId('composer-plus-menu')).not.toBeInTheDocument();
    expect(screen.getByTestId('composer-plus-mode-pico-fast')).toHaveTextContent('快速');
    expect(screen.getByTestId('composer-plus-mode-pico-deep')).toHaveTextContent('深度');
    expect(screen.getByTestId('composer-plan-toggle')).toHaveTextContent('先计划');
    expect(screen.getByTestId('composer-plan-toggle')).toHaveAttribute('aria-pressed', 'false');
    const input = screen.getByTestId('composer-plus-file-input') as HTMLInputElement;
    const click = jest.spyOn(input, 'click');
    fireEvent.click(screen.getByTestId('composer-plus'));
    expect(click).toHaveBeenCalled();
    expect(screen.queryByTestId('composer-plus-menu')).not.toBeInTheDocument();
    expect(screen.queryByText('默认权限')).not.toBeInTheDocument();
    expect(screen.queryByText(/工作空间/)).not.toBeInTheDocument();
  });

  it('先计划 is a pressable toggle next to 快速/深度', () => {
    render(<Landing centerFormOnLanding />);
    const toggle = screen.getByTestId('composer-plan-toggle');
    expect(toggle).toHaveAttribute('aria-pressed', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-pressed', 'true');
  });

  it('plus file input stays in the composer', () => {
    render(<Landing centerFormOnLanding />);
    expect(screen.getByTestId('composer-plus-file-input')).toBeInTheDocument();
    expect(screen.queryByTestId('composer-plus-attach')).not.toBeInTheDocument();
  });
});
