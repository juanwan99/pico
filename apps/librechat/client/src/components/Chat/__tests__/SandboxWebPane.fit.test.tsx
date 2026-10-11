import { act, render, screen } from '@testing-library/react';
import {
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  postPicoSandboxInput,
  streamPicoSandbox,
} from '~/data-provider/pico/api';
import SandboxWebPane from '../SandboxWebPane';

jest.mock('~/data-provider/pico/api', () => ({
  destroyPicoSandboxSession: jest.fn(),
  focusPicoSandboxWindow: jest.fn(),
  getPicoSandboxScreenshot: jest.fn(),
  getPicoSandboxSession: jest.fn(),
  openPicoSandboxDocument: jest.fn(),
  postPicoSandboxInput: jest.fn(),
  streamPicoSandbox: jest.fn(),
}));

/** #1224: the page lays out at the pane's own size, once resizing settles. */
describe('SandboxWebPane fits the pane', () => {
  let resize: () => void = () => undefined;
  const size = { w: 0, h: 0 };

  beforeEach(() => {
    jest.useFakeTimers();
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ url: 'https://example.com/' });
    (streamPicoSandbox as jest.Mock).mockReturnValue(new Promise(() => undefined));
    (postPicoSandboxInput as jest.Mock).mockReset().mockResolvedValue({});
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: () => 'blob:p' });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: jest.fn() });
    Object.defineProperty(HTMLElement.prototype, 'clientWidth', {
      configurable: true,
      get: () => size.w,
    });
    Object.defineProperty(HTMLElement.prototype, 'clientHeight', {
      configurable: true,
      get: () => size.h,
    });
    (window as unknown as { ResizeObserver: unknown }).ResizeObserver = class {
      constructor(cb: () => void) {
        resize = cb;
      }

      observe() {
        resize();
      }

      disconnect() {
        resize = () => undefined;
      }
    };
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it('sends the stage size after resizing settles, and skips tiny changes', async () => {
    size.w = 480;
    size.h = 620;
    render(<SandboxWebPane sessionId="sbox_fit" kind="browser" />);
    await act(async () => {
      await jest.advanceTimersByTimeAsync(500);
    });
    expect(await screen.findByTestId('sandbox-web-viewport')).toBeInTheDocument();
    await act(async () => {
      await jest.advanceTimersByTimeAsync(400);
    });
    expect(postPicoSandboxInput).toHaveBeenCalledWith('sbox_fit', {
      viewport_width: 480,
      viewport_height: 620,
    });

    // Dragging the splitter: many resize events, one call once it settles.
    (postPicoSandboxInput as jest.Mock).mockClear();
    for (const w of [600, 700, 860]) {
      size.w = w;
      act(() => resize());
      await act(async () => {
        await jest.advanceTimersByTimeAsync(100);
      });
    }
    await act(async () => {
      await jest.advanceTimersByTimeAsync(400);
    });
    expect(postPicoSandboxInput).toHaveBeenCalledTimes(1);
    expect(postPicoSandboxInput).toHaveBeenCalledWith('sbox_fit', {
      viewport_width: 860,
      viewport_height: 620,
    });

    (postPicoSandboxInput as jest.Mock).mockClear();
    size.w = 863;
    act(() => resize());
    await act(async () => {
      await jest.advanceTimersByTimeAsync(400);
    });
    expect(postPicoSandboxInput).not.toHaveBeenCalled();
  });
});
