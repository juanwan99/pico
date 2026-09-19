import React from 'react';
import { render, screen } from '@testing-library/react';
import ConvoLink from './ConvoLink';

jest.mock('~/utils', () => ({
  cn: (...classes: Array<string | false | null | undefined>) => classes.filter(Boolean).join(' '),
}));

describe('ConvoLink ledger status badge', () => {
  it('shows the ledger status badge when provided', () => {
    render(
      <ConvoLink
        isActiveConvo={false}
        isPopoverActive={false}
        title="备课"
        ledgerStatus="进行中"
        onRename={() => undefined}
        isSmallScreen={false}
        localize={(key) => key}
      >
        <span aria-hidden />
      </ConvoLink>,
    );
    expect(screen.getByTestId('convo-ledger-status')).toHaveTextContent('进行中');
    expect(screen.getByLabelText('备课，进行中')).toBeInTheDocument();
  });

  it('renders without badge when status is absent', () => {
    render(
      <ConvoLink
        isActiveConvo
        isPopoverActive={false}
        title="空"
        onRename={() => undefined}
        isSmallScreen={false}
        localize={(key) => key}
      >
        <span aria-hidden />
      </ConvoLink>,
    );
    expect(screen.queryByTestId('convo-ledger-status')).not.toBeInTheDocument();
  });

  it('gives the title full width on two lines and stacks the status under it', () => {
    render(
      <ConvoLink
        isActiveConvo={false}
        isPopoverActive={false}
        title="这是一个超长的备课与作业分析任务标题用于验证窄侧栏布局"
        ledgerStatus="已完成"
        onRename={() => undefined}
        isSmallScreen={false}
        localize={(key) => key}
      >
        <span aria-hidden />
      </ConvoLink>,
    );

    const title = screen.getByTestId('convo-title');
    expect(title).toHaveClass('min-w-0', 'w-full', 'line-clamp-2');
    expect(title.parentElement).toHaveClass('flex-col');
    expect(screen.getByTestId('convo-ledger-status')).toHaveClass('self-start', 'shrink-0');
    expect(screen.getByTestId('convo-ledger-status')).not.toHaveClass('truncate');
  });
});
