import { render, screen } from '@testing-library/react';
import RunLoadingIndicator from './RunLoadingIndicator';

describe('RunLoadingIndicator', () => {
  it('announces the current execution state', () => {
    render(<RunLoadingIndicator label="执行中，正在准备产物" />);
    expect(screen.getByRole('status')).toHaveTextContent('执行中，正在准备产物');
  });
});
