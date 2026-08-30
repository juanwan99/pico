import React from 'react';
import { render, screen } from '@testing-library/react';
import MessageContent from '../MessageContent';

jest.mock('~/hooks', () => ({
  useMessageProcess: () => ({ handleScroll: () => undefined, isSubmitting: false }),
  useMemoizedChatContext: () => ({
    chatContext: {},
    effectiveIsSubmitting: false,
  }),
}));

jest.mock('../ContentRender', () => ({
  __esModule: true,
  default: () => <div data-testid="content-render" />,
}));

jest.mock('~/hooks/Pico/usePointsMeter', () => ({
  usePointsMeter: jest.fn(),
}));

const { usePointsMeter } = jest.requireMock('~/hooks/Pico/usePointsMeter') as {
  usePointsMeter: jest.Mock;
};

describe('MessageContent points footer (live content[] path)', () => {
  it('pins 实际 at the end of an assistant reply', () => {
    usePointsMeter.mockReturnValue({
      turnForMessage: (id: string) =>
        id === 'a1' ? { messageId: 'a1', quote: '0.018', actual: '0.042' } : null,
    });
    render(
      <MessageContent
        message={{ messageId: 'a1', isCreatedByUser: false, content: [{ type: 'text', text: '好' }] } as never}
      />,
    );
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('实际 0.042 积分');
    expect(screen.queryByText('未结算')).not.toBeInTheDocument();
  });

  it('keeps 预计 on that reply until tokens land', () => {
    usePointsMeter.mockReturnValue({
      turnForMessage: (id: string) =>
        id === 'a1' ? { messageId: 'a1', quote: '0.018', actual: null } : null,
    });
    render(
      <MessageContent
        message={{ messageId: 'a1', isCreatedByUser: false, content: [{ type: 'text', text: '好' }] } as never}
      />,
    );
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('预计 0.018 积分');
  });
});
