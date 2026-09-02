import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import PicoThinkingChain from '../../components/Chat/Messages/PicoThinkingChain';

describe('PicoThinkingChain', () => {
  it('shows a live placeholder while submitting with no text', () => {
    render(<PicoThinkingChain isSubmitting />);
    expect(screen.getByTestId('pico-thinking-chain')).toHaveTextContent('正在思考…');
    expect(screen.getByTestId('pico-thinking-chain')).toHaveAttribute(
      'data-submitting',
      'true',
    );
    expect(screen.getByTestId('pico-thinking-chain-body').className).toMatch(/line-clamp-3/);
  });

  it('clamps long text to 3 lines until clicked', () => {
    const text = ['a', 'b', 'c', 'd', 'e'].join('\n');
    render(<PicoThinkingChain text={text} />);
    const body = screen.getByTestId('pico-thinking-chain-body');
    expect(body.className).toMatch(/line-clamp-3/);
    fireEvent.click(screen.getByTestId('pico-thinking-chain'));
    expect(screen.getByTestId('pico-thinking-chain')).toHaveAttribute('data-expanded', 'true');
    expect(body.className).toMatch(/max-h-48/);
    expect(body.className).toMatch(/overflow-y-auto/);
  });

  it('renders nothing when idle and empty', () => {
    const { container } = render(<PicoThinkingChain />);
    expect(container).toBeEmptyDOMElement();
  });
});
