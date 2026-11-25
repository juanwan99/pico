import { act, fireEvent, render, screen } from '@testing-library/react';
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

/** The page lays out in CSS pixels, and Chromium renders at the device density. */
describe('SandboxWebPane fits the pane', () => {
  let resize: () => void = () => undefined;
  const size = { w: 0, h: 0 };

  beforeEach(() => {
    jest.useFakeTimers();
    (getPicoSandboxScreenshot as jest.Mock).mockClear();
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

  it('sends the new size without waiting for a timer, caps DPR and skips duplicates', async () => {
    size.w = 480;
    size.h = 620;
    const dpr = Object.getOwnPropertyDescriptor(window, 'devicePixelRatio');
    Object.defineProperty(window, 'devicePixelRatio', { configurable: true, value: 1.5 });
    render(<SandboxWebPane sessionId="sbox_fit" kind="browser" />);
    try {
      await act(async () => {
        await Promise.resolve();
      });
      expect(postPicoSandboxInput).toHaveBeenCalledWith('sbox_fit', {
        viewport_width: 480,
        viewport_height: 620,
        device_pixel_ratio: 1.5,
      });

      (postPicoSandboxInput as jest.Mock).mockClear();
      Object.defineProperty(window, 'devicePixelRatio', { configurable: true, value: 3 });
      await act(async () => {
        for (const w of [600, 700, 860, 860]) {
          size.w = w;
          resize();
        }
      });
      expect(postPicoSandboxInput).toHaveBeenCalledTimes(1);
      expect(postPicoSandboxInput).toHaveBeenCalledWith('sbox_fit', {
        viewport_width: 860,
        viewport_height: 620,
        device_pixel_ratio: 2,
      });
    } finally {
      Object.defineProperty(window, 'devicePixelRatio', dpr!);
    }
  });

  it('confirms a decoded frame, maps clicks in CSS pixels and resumes PNG polling on drop', async () => {
    size.w = 0;
    size.h = 0;
    const { streamPicoSandbox: stream } = jest.requireActual('~/data-provider/pico/api');
    (streamPicoSandbox as jest.Mock).mockImplementation(stream);
    let decoded!: () => void;
    let dropStream!: (reason: Error) => void;
    const reader = {
      read: jest.fn()
        .mockResolvedValueOnce({
          value: 'data: {"jpeg":"abc","width":480,"height":620,"frame_id":"frame_a"}\n\n',
          done: false,
        })
        .mockImplementation(() => new Promise((_resolve, reject) => { dropStream = reject; })),
      cancel: jest.fn().mockResolvedValue(undefined),
    };
    const decode = Object.getOwnPropertyDescriptor(Image.prototype, 'decode');
    const decoderStream = Object.getOwnPropertyDescriptor(globalThis, 'TextDecoderStream');
    const fetch = Object.getOwnPropertyDescriptor(globalThis, 'fetch');
    Object.defineProperty(Image.prototype, 'decode', {
      configurable: true,
      value: () => new Promise<void>((resolve) => { decoded = resolve; }),
    });
    Object.defineProperty(globalThis, 'TextDecoderStream', {
      configurable: true,
      value: class {},
    });
    const fetchMock = jest.fn()
      .mockResolvedValueOnce({
        ok: true,
        body: { pipeThrough: () => ({ getReader: () => reader }) },
      })
      .mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    Object.defineProperty(globalThis, 'fetch', { configurable: true, value: fetchMock });
    const { unmount } = render(<SandboxWebPane sessionId="sbox_fit" kind="browser" />);
    try {
      await act(async () => { await Promise.resolve(); });
      expect(fetchMock).toHaveBeenCalledTimes(1);
      await act(async () => decoded());
      expect(fetchMock).toHaveBeenNthCalledWith(
        2,
        '/api/pico/v1/sandbox/sessions/sbox_fit/input',
        expect.objectContaining({ body: JSON.stringify({ frame_ack: 'frame_a' }) }),
      );
      const img = screen.getByTestId('sandbox-web-viewport');
      Object.defineProperties(img, {
        naturalWidth: { value: 720 },
        naturalHeight: { value: 930 },
      });
      img.getBoundingClientRect = () =>
        ({ left: 0, top: 0, width: 480, height: 620 }) as DOMRect;
      (getPicoSandboxScreenshot as jest.Mock).mockClear();
      await act(async () => {
        fireEvent.click(img, { clientX: 465, clientY: 600 });
        await jest.advanceTimersByTimeAsync(400);
      });
      expect(postPicoSandboxInput).toHaveBeenCalledWith('sbox_fit', { click_x: 465, click_y: 600 });
      expect(getPicoSandboxScreenshot).not.toHaveBeenCalled();

      await act(async () => {
        dropStream(new Error('stream stopped'));
        await jest.advanceTimersByTimeAsync(400);
      });
      expect(getPicoSandboxScreenshot).toHaveBeenCalledTimes(1);
      expect(reader.cancel).toHaveBeenCalled();
    } finally {
      unmount();
      for (const [target, key, descriptor] of [
        [Image.prototype, 'decode', decode],
        [globalThis, 'TextDecoderStream', decoderStream],
        [globalThis, 'fetch', fetch],
      ] as const) {
        if (descriptor) {
          Object.defineProperty(target, key, descriptor);
        } else {
          Reflect.deleteProperty(target, key);
        }
      }
    }
  });
});
