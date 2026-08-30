import React from 'react';
import { render, screen } from '@testing-library/react';
import PointsBar from '../PointsBar';

jest.mock('~/hooks/Pico/usePointsMeter', () => ({
  usePointsMeter: jest.fn(),
}));

const { usePointsMeter } = jest.requireMock('~/hooks/Pico/usePointsMeter') as {
  usePointsMeter: jest.Mock;
};

describe('PointsBar', () => {
  it('renders live quote above the composer without token words', () => {
    usePointsMeter.mockReturnValue({
      phase: 'quote',
      points: '0.048',
      quoteFromChars: jest.fn(),
      turnForMessage: () => null,
      composerLive: true,
    });
    render(<PointsBar />);
    expect(screen.getByTestId('pico-points-bar')).toHaveTextContent('预计 0.048 积分');
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument();
    expect(screen.queryByText('未结算')).not.toBeInTheDocument();
  });

  it('hides on the composer after the turn is no longer live', () => {
    usePointsMeter.mockReturnValue({
      phase: 'idle',
      points: '3.000',
      quoteFromChars: jest.fn(),
      turnForMessage: () => null,
      composerLive: false,
    });
    const { container } = render(<PointsBar />);
    expect(container).toBeEmptyDOMElement();
  });
});
