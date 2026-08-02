import React from 'react';
import { render, screen } from '@testing-library/react';
import ConvoLink from './ConvoLink';

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
        <span>icon</span>
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
        <span>icon</span>
      </ConvoLink>,
    );
    expect(screen.queryByTestId('convo-ledger-status')).not.toBeInTheDocument();
  });
});
