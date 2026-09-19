import { render, screen } from '@testing-library/react';
import SearchStage from '../SearchStage';

jest.mock('~/components/Nav/SearchBar', () => ({
  __esModule: true,
  default: ({ isStage }: { isStage?: boolean }) => (
    <input
      data-testid="nav-search-input"
      data-stage={isStage ? '1' : '0'}
      placeholder="搜索会话和消息"
    />
  ),
}));

describe('SearchStage', () => {
  it('puts a search field in the main pane so /search is not a blank sheet', () => {
    render(
      <SearchStage>
        <p>输入关键字，结果会出现在这里。</p>
      </SearchStage>,
    );
    expect(screen.getByTestId('search-stage')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '搜索' })).toBeInTheDocument();
    expect(screen.getByTestId('nav-search-input')).toHaveAttribute('data-stage', '1');
    expect(screen.getByText('在会话和消息里找')).toBeInTheDocument();
  });
});
