import React from 'react';
import { render, screen } from '@testing-library/react';
import { EModelEndpoint } from 'librechat-data-provider';
import type { TMessageIcon } from '~/common';

jest.mock('librechat-data-provider', () => ({
  ...jest.requireActual('librechat-data-provider'),
  getEndpointField: jest.fn(() => ''),
}));
jest.mock('~/data-provider', () => ({
  useGetEndpointsQuery: jest.fn(() => ({ data: {} })),
}));
jest.mock('~/utils', () => ({
  getIconEndpoint: jest.fn(() => 'openAI'),
  cn: (...args: unknown[]) => args.filter(Boolean).join(' '),
}));

const iconRenderCount = { current: 0 };

jest.mock('~/components/Endpoints/Icon', () => {
  const Icon = (props: Record<string, unknown>) => {
    iconRenderCount.current += 1;
    return <div data-testid="icon" data-user={String(props.isCreatedByUser)} />;
  };
  Icon.displayName = 'Icon';
  return { __esModule: true, default: Icon };
});

jest.mock('../PixelAnimalPicker', () => {
  const PixelAnimalPicker = ({ children }: { children: React.ReactNode }) => (
    <div data-testid="pixel-animal-picker">{children}</div>
  );
  PixelAnimalPicker.displayName = 'PixelAnimalPicker';
  return { __esModule: true, default: PixelAnimalPicker };
});

import MessageIcon from '../MessageIcon';

const aiIconData: TMessageIcon = {
  endpoint: EModelEndpoint.openAI,
  model: 'deepseek-chat',
  iconURL: '/assets/openai.svg',
  modelLabel: 'Pico',
  isCreatedByUser: false,
};

const userIconData: TMessageIcon = {
  ...aiIconData,
  isCreatedByUser: true,
};

describe('MessageIcon chat face', () => {
  beforeEach(() => {
    iconRenderCount.current = 0;
  });

  it('renders the 微与积 mark for AI messages, not Codex/OpenAI assets', () => {
    render(<MessageIcon iconData={aiIconData} />);

    const mark = screen.getByAltText('微与积');
    expect(mark).toHaveAttribute('src', '/assets/weiyuji-mark.svg');
    expect(screen.queryByTestId('icon')).not.toBeInTheDocument();
    expect(screen.queryByTestId('pixel-animal-picker')).not.toBeInTheDocument();
  });

  it('ignores OpenAI/Codex icon URLs on AI messages', () => {
    render(
      <MessageIcon
        iconData={{
          ...aiIconData,
          iconURL: 'https://cdn.openai.com/codex.png',
        }}
      />,
    );

    expect(screen.getByAltText('微与积')).toBeInTheDocument();
  });

  it('wraps the user avatar with the pixel-animal picker', () => {
    render(<MessageIcon iconData={userIconData} />);

    expect(screen.getByTestId('pixel-animal-picker')).toBeInTheDocument();
    expect(screen.getByTestId('icon')).toHaveAttribute('data-user', 'true');
    expect(screen.queryByAltText('微与积')).not.toBeInTheDocument();
  });

  it('does not re-render the user icon when parent passes new object refs with the same fields', () => {
    const { rerender } = render(<MessageIcon iconData={userIconData} />);
    iconRenderCount.current = 0;

    rerender(<MessageIcon iconData={{ ...userIconData }} />);

    expect(iconRenderCount.current).toBe(0);
  });
});
