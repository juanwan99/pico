/**
 * Result-panel isolated webpage: poll sidecar screenshot, click → click_x/y,
 * type visible/password into the sandbox only. Password never leaves this pane
 * into chat / ledger events.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';
import {
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  postPicoSandboxInput,
} from '~/data-provider/pico/api';

const POLL_MS = 1500;
const VIEWPORT_W = 390;
const VIEWPORT_H = 844;

export default function SandboxWebPane({
  sessionId,
  initialUrl,
  initialTitle,
  humanCopy,
}: {
  sessionId: string;
  initialUrl?: string;
  initialTitle?: string;
  humanCopy?: string;
}) {
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [pageUrl, setPageUrl] = useState(initialUrl || '');
  const [pageTitle, setPageTitle] = useState(initialTitle || '');
  const [status, setStatus] = useState('打开中');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [visibleText, setVisibleText] = useState('');
  const secretRef = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);

  const refreshShot = useCallback(async () => {
    const blob = await getPicoSandboxScreenshot(sessionId);
    if (objectUrlRef.current) {
      URL.revokeObjectURL(objectUrlRef.current);
    }
    const next = URL.createObjectURL(blob);
    objectUrlRef.current = next;
    setImageUrl(next);
  }, [sessionId]);

  const refreshMeta = useCallback(async () => {
    try {
      const meta = await getPicoSandboxSession(sessionId);
      if (meta.url) {
        setPageUrl(meta.url);
      }
      if (meta.title) {
        setPageTitle(meta.title);
      }
    } catch {
      /* shot poll is the source of liveness */
    }
  }, [sessionId]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        await refreshShot();
        if (!cancelled) {
          setStatus('请在此画面操作');
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err);
          if (message.includes('404')) {
            setError('隔离会话已结束或不属于当前账号');
            setStatus('已关');
          } else {
            setError('画面暂时不可用，请稍后重试');
          }
        }
      }
    };
    void tick();
    void refreshMeta();
    const id = window.setInterval(() => {
      void tick();
      void refreshMeta();
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
        objectUrlRef.current = null;
      }
    };
  }, [refreshMeta, refreshShot]);

  const sendInput = async (body: {
    click_x?: number;
    click_y?: number;
    text?: string;
    secret?: string;
  }) => {
    setBusy(true);
    setError(null);
    try {
      const meta = await postPicoSandboxInput(sessionId, body);
      if (meta.url) {
        setPageUrl(meta.url);
      }
      if (meta.title) {
        setPageTitle(meta.title);
      }
      await refreshShot();
      setStatus('已送进隔离浏览器');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message.includes('404') ? '隔离会话不存在或无权限' : '操作未送出，请重试');
    } finally {
      setBusy(false);
    }
  };

  const onViewportClick = async (ev: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current;
    if (!img || busy) {
      return;
    }
    const rect = img.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) {
      return;
    }
    const nw = img.naturalWidth || VIEWPORT_W;
    const nh = img.naturalHeight || VIEWPORT_H;
    const x = Math.round((ev.clientX - rect.left) * (nw / rect.width));
    const y = Math.round((ev.clientY - rect.top) * (nh / rect.height));
    await sendInput({ click_x: x, click_y: y });
  };

  const sendVisible = async () => {
    const value = visibleText;
    if (!value) {
      return;
    }
    setVisibleText('');
    await sendInput({ text: value });
  };

  const sendSecret = async () => {
    const el = secretRef.current;
    const value = el?.value || '';
    if (!value) {
      return;
    }
    if (el) {
      el.value = '';
    }
    await sendInput({ secret: value });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="sandbox-web-pane">
      <div className="border-b border-black/[0.05] px-2 py-1.5">
        <p className="truncate text-[11px] text-[#6b6b6b]" title={pageUrl || undefined}>
          {pageTitle || '隔离网页'}
          {pageUrl ? ` · ${pageUrl}` : ''}
        </p>
        <p className="mt-0.5 text-[11px] leading-snug text-[#3d3d3d]" data-testid="sandbox-web-copy">
          {humanCopy || '请在此画面自行登录，不要在聊天里发送密码'}
        </p>
        <p className="mt-0.5 text-[10px] text-[#9a9a9a]" data-testid="sandbox-web-status">
          {status}
        </p>
      </div>
      <div className="min-h-0 flex-1 overflow-auto bg-[#111]">
        {imageUrl ? (
          <img
            ref={imgRef}
            src={imageUrl}
            alt="隔离浏览器画面"
            width={VIEWPORT_W}
            onClick={(ev) => void onViewportClick(ev)}
            className="mx-auto block w-full max-w-[390px] cursor-crosshair bg-white"
            data-testid="sandbox-web-viewport"
          />
        ) : (
          <div className="flex min-h-[280px] items-center justify-center text-[#9a9a9a]">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        )}
      </div>
      <form
        className="space-y-1.5 border-t border-black/[0.06] px-2 py-2"
        onSubmit={(ev) => {
          ev.preventDefault();
          void sendVisible();
        }}
        autoComplete="off"
      >
        <label className="block text-[11px] text-[#6b6b6b]">
          可见输入
          <input
            value={visibleText}
            onChange={(e) => setVisibleText(e.target.value)}
            className="mt-0.5 w-full rounded-md border border-black/[0.08] bg-white px-2 py-1.5 text-[12px] outline-none"
            data-testid="sandbox-web-text"
            autoComplete="off"
          />
        </label>
        <label className="block text-[11px] text-[#6b6b6b]">
          密码（只进隔离会话）
          <input
            ref={secretRef}
            type="password"
            className="mt-0.5 w-full rounded-md border border-black/[0.08] bg-white px-2 py-1.5 text-[12px] outline-none"
            data-testid="sandbox-web-password"
            autoComplete="new-password"
          />
        </label>
        <div className="flex gap-1">
          <button
            type="submit"
            disabled={busy}
            className="rounded-md bg-[#1a1a1a] px-2.5 py-1 text-[11.5px] font-medium text-white disabled:opacity-50"
            data-testid="sandbox-web-send-text"
          >
            送可见字
          </button>
          <button
            type="button"
            disabled={busy}
            className="rounded-md border border-black/[0.08] px-2.5 py-1 text-[11.5px] disabled:opacity-50"
            onClick={() => void sendSecret()}
            data-testid="sandbox-web-send-password"
          >
            送密码
          </button>
        </div>
        {error ? (
          <p className="text-[11px] text-red-700" role="alert" data-testid="sandbox-web-error">
            {error}
          </p>
        ) : null}
      </form>
    </div>
  );
}
