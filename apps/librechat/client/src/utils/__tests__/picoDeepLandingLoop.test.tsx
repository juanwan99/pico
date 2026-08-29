/**
 * Regression: clicking 深度 (or hub-preset pico-deep) must not hit React #185.
 * Old path: applyModel wrote PENDING, effect depended on chatCtx, consume
 * re-applied, Recoil new object, infinite setState.
 */
import React, { useState } from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import Landing from '~/components/Chat/Landing';
import { queuePendingModel } from '~/utils/picoModelPref';

type Convo = { conversationId: string; endpoint: string; model: string };

const mockChat: {
  current: {
    conversation: Convo;
    setConversation: (updater: (prev: Convo | null) => Convo | null | undefined) => void;
  } | null;
} = { current: null };

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

jest.mock('~/components/ui/pico-icons', () => ({
  PicoIcon: () => <span data-testid="pico-icon" />,
}));

jest.mock('~/Providers', () => ({
  useOptionalChatFormContext: () => ({ setValue: jest.fn() }),
  useOptionalChatContext: () => mockChat.current,
}));

function Harness({ onRender }: { onRender: () => void }) {
  const [convo, setConvo] = useState<Convo>({
    conversationId: 'new',
    endpoint: 'openAI',
    model: 'pico-fast',
  });
  onRender();
  mockChat.current = {
    conversation: convo,
    setConversation: (updater) => {
      setConvo((prev) => updater(prev) ?? prev);
    },
  };
  return <Landing centerFormOnLanding />;
}

describe('Landing pico-deep does not React #185', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('click 深度 settles without max-update-depth', () => {
    let renders = 0;
    render(<Harness onRender={() => renders++} />);
    fireEvent.click(screen.getByTestId('composer-plus-mode-pico-deep'));
    expect(screen.getByTestId('composer-plus')).toBeInTheDocument();
    expect(renders).toBeLessThan(20);
    expect(localStorage.getItem('pico:modelMode')).toBe('pico-deep');
    expect(sessionStorage.getItem('pico:pendingModel')).toBeNull();
    expect(mockChat.current?.conversation.model).toBe('pico-deep');
  });

  it('preset pico-deep (hub PENDING) consumes once', async () => {
    queuePendingModel('pico-deep');
    let renders = 0;
    render(<Harness onRender={() => renders++} />);
    await waitFor(() => {
      expect(mockChat.current?.conversation.model).toBe('pico-deep');
    });
    expect(renders).toBeLessThan(20);
    expect(localStorage.getItem('pico:modelMode')).toBe('pico-deep');
    expect(sessionStorage.getItem('pico:pendingModel')).toBeNull();
    expect(screen.getByTestId('composer-plus')).toBeInTheDocument();
  });
});
