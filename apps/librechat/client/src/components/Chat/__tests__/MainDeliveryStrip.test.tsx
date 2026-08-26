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
});
