import React from 'react';
import { render, screen } from '@testing-library/react';
import MessageContent from '~/components/Messages/MessageContent';
import type { TMessage } from 'librechat-data-provider';

jest.mock('~/components/Messages/ContentRender', () => ({
  __esModule: true,
  default: () => <div data-testid="content-render" />,
}));

jest.mock('~/hooks', () => ({
  useMessageProcess: () => ({ handleScroll: () => undefined, isSubmitting: false }),
  useMemoizedChatContext: () => ({ chatContext: {}, effectiveIsSubmitting: false }),
}));

jest.mock('~/hooks/Pico/usePointsMeter', () => ({
  usePointsMeter: () => ({
    turnForMessage: (id?: string | null) =>
      id === 'a1' ? { messageId: 'a1', quote: '0.018', actual: '0.042' } : null,
  }),
}));

describe('MessageContent points footer', () => {
  it('pins 实际 at the end of a content-parts assistant row', () => {
    const message = {
      messageId: 'a1',
      isCreatedByUser: false,
      content: [{ type: 'text', text: '好' }],
    } as TMessage;
    render(<MessageContent message={message} />);
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('实际 0.042 积分');
    expect(screen.queryByText('未结算')).not.toBeInTheDocument();
  });
});
