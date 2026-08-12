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

  it('truncates a long title before the fixed status column', () => {
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

    expect(screen.getByTestId('convo-title')).toHaveClass('min-w-0', 'truncate');
    expect(screen.getByTestId('convo-ledger-status')).toHaveClass('shrink-0', 'max-w-[4.5rem]');
  });
});
