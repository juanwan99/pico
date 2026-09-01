import { render, screen } from '@testing-library/react';
import RunLoadingIndicator from './RunLoadingIndicator';

describe('RunLoadingIndicator', () => {
  it('announces the current execution state', () => {
    render(<RunLoadingIndicator label="执行中，正在准备产物" />);
    expect(screen.getByRole('status')).toHaveTextContent('执行中，正在准备产物');
  });

  it('can announce a parked wait without a spinner', () => {
    const { container } = render(<RunLoadingIndicator label="在等你选" spin={false} />);
    expect(screen.getByRole('status')).toHaveTextContent('在等你选');
    expect(container.querySelector('.animate-spin')).toBeNull();
  });
});
