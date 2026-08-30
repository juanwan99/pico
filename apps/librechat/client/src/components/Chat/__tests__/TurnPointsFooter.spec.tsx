import React from 'react';
import { render, screen } from '@testing-library/react';
import TurnPointsFooter from '../TurnPointsFooter';

jest.mock('~/hooks/Pico/usePointsMeter', () => ({
  usePointsMeter: jest.fn(),
}));

const { usePointsMeter } = jest.requireMock('~/hooks/Pico/usePointsMeter') as {
  usePointsMeter: jest.Mock;
};

describe('TurnPointsFooter', () => {
  it('does not render on user turns', () => {
    usePointsMeter.mockReturnValue({
      turnForMessage: () => ({ messageId: 'u1', quote: '0.018', actual: null }),
    });
    const { container } = render(<TurnPointsFooter messageId="u1" isCreatedByUser />);
    expect(container).toBeEmptyDOMElement();
  });

  it('pins 预计 on an assistant turn until 实际 arrives', () => {
    usePointsMeter.mockReturnValue({
      turnForMessage: (id: string) =>
        id === 'a1' ? { messageId: 'a1', quote: '0.018', actual: null } : null,
    });
    render(<TurnPointsFooter messageId="a1" isCreatedByUser={false} />);
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('预计 0.018 积分');
    expect(screen.queryByText('未结算')).not.toBeInTheDocument();
  });

  it('keeps 实际 on that round after tokens land', () => {
    usePointsMeter.mockReturnValue({
      turnForMessage: (id: string) =>
        id === 'a1' ? { messageId: 'a1', quote: '0.018', actual: '0.042' } : null,
    });
    render(<TurnPointsFooter messageId="a1" isCreatedByUser={false} />);
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('实际 0.042 积分');
  });

  it('does not wipe a previous round when looking up another message', () => {
    const turns = {
      a1: { messageId: 'a1', quote: '0.018', actual: '0.042' },
      a2: { messageId: 'a2', quote: '0.024', actual: null },
    };
    usePointsMeter.mockReturnValue({
      turnForMessage: (id: string) => turns[id as keyof typeof turns] ?? null,
    });
    const { rerender } = render(<TurnPointsFooter messageId="a1" isCreatedByUser={false} />);
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('实际 0.042 积分');
    rerender(<TurnPointsFooter messageId="a2" isCreatedByUser={false} />);
    expect(screen.getByTestId('pico-turn-points')).toHaveTextContent('预计 0.024 积分');
  });
});
