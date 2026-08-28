import { render, screen } from '@testing-library/react';
import type { PicoArtifact, PicoRunEvent } from '~/data-provider/pico/api';
import MainDeliveryStrip from '../MainDeliveryStrip';

jest.mock('~/data-provider/pico/api', () => ({
  getPicoArtifactContent: jest.fn(),
}));
jest.mock('~/utils', () => ({
  cn: (...values: Array<string | false | null | undefined>) => values.filter(Boolean).join(' '),
}));

function searchEvent(): PicoRunEvent {
  return {
    id: 'search-1',
    run_id: 'run-1',
    seq: 1,
    type: 'search.sources',
    payload: {
      tool: 'web_search',
      honest_miss: false,
      sources: [{ title: 'Gov', url: 'https://www.gov.cn/a' }],
    },
  };
}

function artifact(): PicoArtifact {
  return {
    id: 'art-1',
    title: 'note.html',
    kind: 'html',
  };
}

describe('MainDeliveryStrip column', () => {
  it('keeps sources-only 来源 inside the same max-width column as files', () => {
    render(<MainDeliveryStrip runEvents={[searchEvent()]} artifacts={[]} />);
    const sources = screen.getByTestId('pico-search-sources');
    const strip = screen.getByTestId('main-delivery-strip');
    expect(strip).toContainElement(sources);
    expect(strip.className).toContain('max-w-[797px]');
  });

  it('keeps files and sources in one column', () => {
    render(<MainDeliveryStrip runEvents={[searchEvent()]} artifacts={[artifact()]} />);
    const strip = screen.getByTestId('main-delivery-strip');
    expect(strip).toContainElement(screen.getByTestId('pico-search-sources'));
    expect(strip).toContainElement(screen.getByTestId('main-delivery-item'));
    expect(strip.className).toContain('max-w-[797px]');
  });

  it('shows one row when the same filename was written many times', () => {
    const dupes = Array.from({ length: 8 }, (_, index) => ({
      id: `art-${index}`,
      title: 'Live Observe.pptx',
      kind: 'pptx',
    }));
    render(<MainDeliveryStrip artifacts={dupes} />);
    expect(screen.getAllByTestId('main-delivery-item')).toHaveLength(1);
    expect(screen.getByText('成品 · 可下载文件（1）')).toBeInTheDocument();
  });

  it('does not list sidecar cover images next to a pptx', () => {
    render(
      <MainDeliveryStrip
        artifacts={[
          { id: 'deck', title: '办公尺752.pptx', kind: 'pptx' },
          { id: 'cover', title: '决策会封面图.jpg', kind: 'jpg' },
        ]}
      />,
    );
    expect(screen.getAllByTestId('main-delivery-item')).toHaveLength(1);
    expect(screen.getByText('办公尺752.pptx')).toBeInTheDocument();
    expect(screen.queryByText('决策会封面图.jpg')).not.toBeInTheDocument();
    expect(screen.getByText('成品 · 可下载文件（1）')).toBeInTheDocument();
  });
});
