import { collectPicoSandboxSession } from '../picoSandboxSession';
import type { PicoRunEvent } from '~/data-provider/pico/api';

function event(type: string, payload: Record<string, unknown>): PicoRunEvent {
  return { id: type, run_id: 'run-1', seq: 1, type, payload };
}

describe('collectPicoSandboxSession', () => {
  it('reads sandbox.session from the ledger', () => {
    const view = collectPicoSandboxSession([
      event('sandbox.session', {
        session_id: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
        url: 'https://example.com/',
        title: 'Example Domain',
        human_copy: '请在此画面自行登录，不要在聊天里发送密码',
      }),
    ]);
    expect(view).toEqual({
      sessionId: 'sbox_aaaaaaaaaaaaaaaaaaaaaaaa',
      url: 'https://example.com/',
      title: 'Example Domain',
      humanCopy: '请在此画面自行登录，不要在聊天里发送密码',
    });
  });

  it('parses sandbox_browser_open tool.result JSON', () => {
    const view = collectPicoSandboxSession([
      event('tool.result', {
        tool: 'sandbox_browser_open',
        ok: true,
        result: JSON.stringify({
          session_id: 'sbox_bbbbbbbbbbbbbbbbbbbbbbbb',
          url: 'https://example.com/',
          title: 'Example Domain',
        }),
      }),
    ]);
    expect(view?.sessionId).toBe('sbox_bbbbbbbbbbbbbbbbbbbbbbbb');
    expect(view?.url).toBe('https://example.com/');
  });

  it('ignores invented ids and never surfaces password fields', () => {
    const view = collectPicoSandboxSession([
      event('sandbox.session', {
        session_id: 'not-a-session',
        password: 'should-not-leak',
      }),
      event('tool.result', {
        tool: 'web_search',
        result: JSON.stringify({ session_id: 'sbox_cccccccccccccccccccccccc' }),
      }),
    ]);
    expect(view).toBeNull();
  });
});
