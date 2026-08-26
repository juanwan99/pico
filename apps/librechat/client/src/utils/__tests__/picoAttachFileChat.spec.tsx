import React from 'react';
import { render, screen } from '@testing-library/react';
import { RecoilRoot } from 'recoil';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EModelEndpoint, mergeFileConfig } from 'librechat-data-provider';
import type { TEndpointsConfig } from 'librechat-data-provider';
import AttachFileChat from '~/components/Chat/Input/Files/AttachFileChat';

const mockEndpointsConfig: TEndpointsConfig = {
  [EModelEndpoint.agents]: { userProvide: false, order: 1 },
};

const mockFileConfig = mergeFileConfig({
  endpoints: {
    [EModelEndpoint.agents]: { fileLimit: 20 },
    default: { fileLimit: 10 },
  },
});

jest.mock('~/data-provider', () => ({
  useGetEndpointsQuery: () => ({ data: mockEndpointsConfig }),
  useGetFileConfig: ({ select }: { select?: (data: unknown) => unknown }) => ({
    data: select != null ? select(mockFileConfig) : mockFileConfig,
  }),
  useGetAgentByIdQuery: () => ({ data: undefined }),
  useGetStartupConfig: () => ({ data: { sharePointFilePickerEnabled: false } }),
}));

jest.mock('~/Providers', () => ({
  useAgentsMapContext: () => ({}),
}));

jest.mock('~/components/Chat/Input/Files/AttachFileMenu', () => {
  return function MockAttachFileMenu() {
    return <div data-testid="attach-file-menu" />;
  };
});

jest.mock('~/components/Chat/Input/Files/AttachFile', () => {
  return function MockAttachFile() {
    return <div data-testid="attach-file" />;
  };
});

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

describe('AttachFileChat (Pico paperclip)', () => {
  it('opens a one-click attach control instead of the destination menu', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <RecoilRoot>
          <AttachFileChat
            conversation={{ endpoint: EModelEndpoint.agents, agent_id: 'pico' } as never}
            disableInputs={false}
            files={new Map()}
            setFiles={() => {}}
            setFilesLoading={() => {}}
          />
        </RecoilRoot>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId('attach-file')).toBeInTheDocument();
    expect(screen.queryByTestId('attach-file-menu')).not.toBeInTheDocument();
  });
});
