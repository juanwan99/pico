import { act, fireEvent, render, screen } from '@testing-library/react';
import {
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  holdPicoSandboxSession,
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

/** #1230: 「AI 正在操作 · 接管」→ stop the task + hold the page →「交还 AI」. */
describe('SandboxWebPane takeover', () => {
  beforeEach(() => {
    (getPicoSandboxScreenshot as jest.Mock).mockResolvedValue(
      new Blob([new Uint8Array([137, 80, 78, 71])], { type: 'image/png' }),
    );
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({
      url: 'https://example.com/',
      human_hold: false,
      ai_acting: true,
    });
    (streamPicoSandbox as jest.Mock).mockReturnValue(new Promise(() => undefined));
    (holdPicoSandboxSession as jest.Mock).mockReset();
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: () => 'blob:p' });
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: jest.fn() });
  });

  it('shows the bar only while the AI is running and touched this page', async () => {
    const { rerender } = render(<SandboxWebPane sessionId="sbox_t" kind="browser" />);
    await screen.findByTestId('sandbox-web-viewport');
    expect(screen.queryByTestId('sandbox-takeover-bar')).not.toBeInTheDocument();
    rerender(<SandboxWebPane sessionId="sbox_t" kind="browser" aiBusy />);
    expect(await screen.findByTestId('sandbox-takeover-bar')).toHaveTextContent('AI 正在操作');
  });

  it('接管 stops the task and holds the page; 交还 AI releases it', async () => {
    const onTakeOver = jest.fn();
    (holdPicoSandboxSession as jest.Mock)
      .mockResolvedValueOnce({ human_hold: true, ai_acting: false })
      .mockResolvedValueOnce({ human_hold: false, ai_acting: false });
    render(<SandboxWebPane sessionId="sbox_t" kind="browser" aiBusy onTakeOver={onTakeOver} />);
    const takeOver = await screen.findByTestId('sandbox-takeover');
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ human_hold: true, ai_acting: false });
    await act(async () => {
      fireEvent.click(takeOver);
    });
    expect(onTakeOver).toHaveBeenCalledTimes(1);
    expect(holdPicoSandboxSession).toHaveBeenCalledWith('sbox_t', true);
    expect(screen.getByTestId('sandbox-takeover-bar')).toHaveTextContent('你在操作');

    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ human_hold: false, ai_acting: false });
    await act(async () => {
      fireEvent.click(screen.getByTestId('sandbox-handback'));
    });
    expect(holdPicoSandboxSession).toHaveBeenLastCalledWith('sbox_t', false);
    expect(onTakeOver).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('sandbox-takeover-bar')).not.toBeInTheDocument();
  });

  it('#1238: the hand-back node shows on an idle page, not while held or while the AI works', async () => {
    const node = <div data-testid="hand-back-node" />;
    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ human_hold: false, ai_acting: true });
    const { rerender } = render(<SandboxWebPane sessionId="sbox_t" kind="browser" handBack={node} />);
    expect(await screen.findByTestId('hand-back-node')).toBeInTheDocument();
    rerender(<SandboxWebPane sessionId="sbox_t" kind="browser" aiBusy handBack={node} />);
    expect(screen.queryByTestId('hand-back-node')).not.toBeInTheDocument();
    expect(screen.getByTestId('sandbox-takeover-bar')).toBeInTheDocument();

    (getPicoSandboxSession as jest.Mock).mockResolvedValue({ human_hold: true, ai_acting: false });
    rerender(<SandboxWebPane sessionId="sbox_x" kind="browser" handBack={node} />);
    expect(await screen.findByTestId('sandbox-handback')).toBeInTheDocument();
    expect(screen.queryByTestId('hand-back-node')).not.toBeInTheDocument();
  });
});
