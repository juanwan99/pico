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
  it('renders quote above the composer without token words', () => {
    usePointsMeter.mockReturnValue({
      phase: 'quote',
      points: '0.048',
      quoteFromChars: jest.fn(),
    });
    render(<PointsBar />);
    expect(screen.getByTestId('pico-points-bar')).toHaveTextContent('预计 0.048 积分');
    expect(screen.queryByText(/token/i)).not.toBeInTheDocument();
  });

  it('renders settled actuals', () => {
    usePointsMeter.mockReturnValue({
      phase: 'settled',
      points: '3.000',
      quoteFromChars: jest.fn(),
    });
    render(<PointsBar />);
    expect(screen.getByTestId('pico-points-bar')).toHaveTextContent('实际 3.000 积分');
  });

  it('hides when idle', () => {
    usePointsMeter.mockReturnValue({
      phase: 'idle',
      points: null,
      quoteFromChars: jest.fn(),
    });
    const { container } = render(<PointsBar />);
    expect(container).toBeEmptyDOMElement();
  });
});
