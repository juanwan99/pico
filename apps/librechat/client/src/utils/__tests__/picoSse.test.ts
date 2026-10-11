import { splitSseEvents } from '../picoSse';

describe('splitSseEvents (#1215 live pane)', () => {
  it('returns whole events and keeps the unfinished tail', () => {
    const { events, rest } = splitSseEvents<{ jpeg?: string; ping?: boolean }>(
      'data: {"jpeg":"AAA"}\n\ndata: {"ping":true}\n\ndata: {"jpe',
    );
    expect(events).toEqual([{ jpeg: 'AAA' }, { ping: true }]);
    expect(rest).toBe('data: {"jpe');
    const next = splitSseEvents<{ jpeg?: string }>(`${rest}g":"BBB"}\n\n`);
    expect(next.events).toEqual([{ jpeg: 'BBB' }]);
    expect(next.rest).toBe('');
  });

  it('skips torn JSON and non-data lines', () => {
    const { events } = splitSseEvents(': comment\n\ndata: {bad\n\ndata: {"poll":true}\n\n');
    expect(events).toEqual([{ poll: true }]);
  });
});
