import React from 'react';
import { RecoilRoot } from 'recoil';
import { render, screen } from '@testing-library/react';
import type { TMessage } from 'librechat-data-provider';
import MultiMessage from '../MultiMessage';

jest.mock('../Message', () => ({
  __esModule: true,
  default: () => <div data-testid="row-legacy" />,
}));

jest.mock('../MessageParts', () => ({
  __esModule: true,
  default: () => <div data-testid="row-parts" />,
}));

jest.mock('~/components/Messages/MessageContent', () => ({
  __esModule: true,
  default: () => <div data-testid="row-content" />,
}));

function renderTree(message: TMessage) {
  return render(
    <RecoilRoot>
      <MultiMessage
        messageId={message.messageId}
        messagesTree={[message]}
        currentEditId={null}
        setCurrentEditId={() => undefined}
      />
    </RecoilRoot>,
  );
}

describe('MultiMessage points path', () => {
  it('routes Pi/agents content rows through MessageContent (not Message.tsx)', () => {
    renderTree({
      messageId: 'a1',
      parentMessageId: 'u1',
      isCreatedByUser: false,
      endpoint: 'agents',
      content: [{ type: 'text', text: '好' }],
      children: [],
    } as TMessage);
    expect(screen.getByTestId('row-content')).toBeInTheDocument();
    expect(screen.queryByTestId('row-legacy')).not.toBeInTheDocument();
    expect(screen.queryByTestId('row-parts')).not.toBeInTheDocument();
  });

  it('routes text-only rows through Message.tsx', () => {
    renderTree({
      messageId: 'a2',
      parentMessageId: 'u2',
      isCreatedByUser: false,
      endpoint: 'agents',
      text: '好',
      children: [],
    } as TMessage);
    expect(screen.getByTestId('row-legacy')).toBeInTheDocument();
    expect(screen.queryByTestId('row-content')).not.toBeInTheDocument();
  });
});
