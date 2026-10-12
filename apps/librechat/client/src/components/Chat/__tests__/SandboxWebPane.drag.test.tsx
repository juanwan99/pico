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
  holdPicoSandboxSession: jest.fn(),
  openPicoSandboxDocument: jest.fn(),
  postPicoSandboxInput: jest.fn(),
  streamPicoSandbox: jest.fn(),
}));

if (!('PointerEvent' in window)) {
  // jsdom without PointerEvent: a MouseEvent carries clientX / button the same way.
  Object.defineProperty(window, 'PointerEvent', { configurable: true, value: MouseEvent });
}

/** #1236: the teacher drags a slider check on the pane — press, move, release. */
describe('SandboxWebPane drag', () => {
  beforeEach(() => {
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ url: 'https://example.com/' });
    (streamPicoSandbox as jest.Mock).mockReturnValue(new Promise(() => undefined));
    (postPicoSandboxInput as jest.Mock).mockReset().mockResolvedValue({});
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: () => 'blob:p' });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: jest.fn() });
  });

  const viewport = async () => {
    render(<SandboxWebPane sessionId="sbox_d" kind="browser" />);
    const img = await screen.findByTestId('sandbox-web-viewport');
    // Pane shows the 1280×800 page at half size.
    img.getBoundingClientRect = () =>
      ({ left: 0, top: 0, width: 640, height: 400, right: 640, bottom: 400 }) as DOMRect;
    return img;
  };

  it('sends press → moves → release in page pixels, and no click after the drag', async () => {
    const img = await viewport();
    await act(async () => {
      fireEvent.pointerDown(img, { button: 0, clientX: 50, clientY: 100 });
      fireEvent.pointerMove(img, { clientX: 52, clientY: 100 });
    });
    expect(postPicoSandboxInput).not.toHaveBeenCalled();
    await act(async () => {
      fireEvent.pointerMove(img, { clientX: 100, clientY: 100 });
    });
    await act(async () => {
      fireEvent.pointerUp(img, { clientX: 150, clientY: 101 });
      fireEvent.click(img, { clientX: 150, clientY: 101 });
    });
    const calls = (postPicoSandboxInput as jest.Mock).mock.calls.map((c) => c[1]);
    expect(calls).toEqual([
      { drag: 'down', click_x: 100, click_y: 200 },
      { drag: 'move', click_x: 200, click_y: 200 },
      { drag: 'up', click_x: 300, click_y: 202 },
    ]);
  });

  it('a press that does not travel stays a click', async () => {
    const img = await viewport();
    await act(async () => {
      fireEvent.pointerDown(img, { button: 0, clientX: 50, clientY: 100 });
      fireEvent.pointerUp(img, { clientX: 51, clientY: 100 });
      fireEvent.click(img, { clientX: 51, clientY: 100 });
    });
    expect((postPicoSandboxInput as jest.Mock).mock.calls.map((c) => c[1])).toEqual([
      { click_x: 102, click_y: 200 },
    ]);
  });
});
