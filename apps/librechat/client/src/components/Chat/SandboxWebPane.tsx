/**
 * Result-panel isolated webpage: poll sidecar screenshot, click → click_x/y.
 * Dead session: honest copy + reopen. Login chrome only when the live page
 * actually has a text/password field. Password never leaves this pane.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';
import {
  destroyPicoSandboxSession,
  focusPicoSandboxWindow,
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  openPicoSandboxDocument,
  postPicoSandboxInput,
  type PicoSandboxWindow,
} from '~/data-provider/pico/api';

const POLL_MS = 1500;
const VIEWPORT_W = 1280;
const VIEWPORT_H = 800;

export default function SandboxWebPane({
  sessionId,
  initialUrl,
  initialTitle,
  humanCopy,
  zoom = 1,
  onWheelZoom,
  kind,
  onDestroyed,
  onReopen,
}: {
  sessionId: string;
  initialUrl?: string;
  initialTitle?: string;
  humanCopy?: string;
  kind?: string;
  /** 1 = fit the pane width (fullscreen fills the stage, not a 390 strip). */
  zoom?: number;
  onWheelZoom?: (event: React.WheelEvent) => void;
  onDestroyed?: () => void;
  onReopen?: (args: { url: string; kind?: string }) => void;
}) {
  const [windows, setWindows] = useState<PicoSandboxWindow[]>([]);
  const [files, setFiles] = useState<Array<{ name: string }>>([]);
  const [focusedKind, setFocusedKind] = useState(kind || 'browser');
  const isOffice = Boolean(focusedKind && focusedKind !== 'browser');
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [pageUrl, setPageUrl] = useState(initialUrl || '');
  const [pageTitle, setPageTitle] = useState(initialTitle || '');
  const [status, setStatus] = useState('打开中');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [live, setLive] = useState<'loading' | 'live' | 'dead'>('loading');
  const [hasTextInput, setHasTextInput] = useState(false);
  const [hasPasswordInput, setHasPasswordInput] = useState(false);
  const [chromeOpen, setChromeOpen] = useState(false);
  const [visibleText, setVisibleText] = useState('');
  const secretRef = useRef<HTMLInputElement>(null);
  const objectUrlRef = useRef<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const liveRef = useRef(live);
  liveRef.current = live;

  const applyMeta = useCallback((meta: {
    url?: string;
    title?: string;
    windows?: PicoSandboxWindow[];
    kind?: string;
    files?: Array<{ name: string }>;
    has_text_input?: boolean;
    has_password_input?: boolean;
  }) => {
    if (meta.url) {
      setPageUrl(meta.url);
    }
    if (meta.title) {
      setPageTitle(meta.title);
    }
    if (Array.isArray(meta.windows)) {
      setWindows(meta.windows);
    }
    if (meta.kind) {
      setFocusedKind(meta.kind);
    }
    if (Array.isArray(meta.files)) {
      setFiles(meta.files);
    }
    if (typeof meta.has_text_input === 'boolean') {
      setHasTextInput(meta.has_text_input);
    }
    if (typeof meta.has_password_input === 'boolean') {
      setHasPasswordInput(meta.has_password_input);
    }
  }, []);

  const markDead = useCallback(() => {
    setLive('dead');
    setStatus('已关');
    setError(null);
    setHasTextInput(false);
    setHasPasswordInput(false);
    setChromeOpen(false);
  }, []);

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
      applyMeta(meta);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('404')) {
        markDead();
      }
    }
  }, [applyMeta, markDead, sessionId]);

  useEffect(() => {
    let cancelled = false;
    const tick = async () => {
      try {
        await refreshShot();
        if (!cancelled) {
          setLive('live');
          setStatus('请在此画面操作');
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : String(err);
          if (message.includes('404')) {
            markDead();
          } else {
            setError('画面暂时不可用，请稍后重试');
          }
        }
      }
    };
    void tick();
    void refreshMeta();
    const id = window.setInterval(() => {
      if (cancelled || liveRef.current === 'dead') {
        return;
      }
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
  }, [markDead, refreshMeta, refreshShot]);

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
      applyMeta(meta);
      await refreshShot();
      setLive('live');
      setStatus('已送进隔离浏览器');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('404')) {
        markDead();
      } else {
        setError('操作未送出，请重试');
      }
    } finally {
      setBusy(false);
    }
  };

  const onViewportClick = async (ev: React.MouseEvent<HTMLImageElement>) => {
    const img = imgRef.current;
    if (!img || busy || live !== 'live') {
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

  const switchWindow = async (next: PicoSandboxWindow) => {
    setBusy(true);
    try {
      const meta = await focusPicoSandboxWindow(sessionId, {
        window_id: next.window_id,
        kind: next.kind,
      });
      applyMeta(meta);
      await refreshShot();
      setLive('live');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('404') || message.includes('session_not_found')) {
        markDead();
      } else {
        setError('切窗失败');
      }
    } finally {
      setBusy(false);
    }
  };

  const closeWindow = async () => {
    setBusy(true);
    try {
      await destroyPicoSandboxSession(sessionId);
      markDead();
      onDestroyed?.();
    } catch {
      markDead();
    } finally {
      setBusy(false);
      setChromeOpen(false);
    }
  };

  const showLogin =
    live === 'live' && !isOffice && focusedKind === 'browser' && (hasTextInput || hasPasswordInput);

  if (live === 'dead') {
    return (
      <div
        className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 bg-[#fafafa] px-4 text-center"
        data-testid="sandbox-web-pane"
        data-live="dead"
      >
        <div data-testid="sandbox-dead">
          <p className="text-[15px] font-medium text-[#1a1a1a]" data-testid="sandbox-dead-copy">
            沙箱已关闭
          </p>
          <p className="mt-1 max-w-[16rem] text-[12px] leading-relaxed text-[#8c8c8c]">
            窗口已结束。文件仍在这台老师盘上，可以重新打开网页或文档。
          </p>
        </div>
        <button
          type="button"
          data-testid="sandbox-reopen"
          className="rounded-lg bg-[#1a1a1a] px-3.5 py-1.5 text-[13px] font-medium text-white"
          onClick={() => onReopen?.({ url: pageUrl, kind: focusedKind })}
        >
          重新打开
        </button>
      </div>
    );
  }

  return (
    <div className="relative flex min-h-0 flex-1 flex-col" data-testid="sandbox-web-pane" data-live={live}>
      {windows.length > 1 ? (
        <div
          className="flex flex-wrap gap-1 border-b border-black/[0.05] bg-[#f4f4f4] px-2 py-1"
          data-testid="sandbox-window-bar"
        >
          {windows.map((item) => (
            <button
              key={item.window_id}
              type="button"
              data-testid={`sandbox-window-${item.kind}`}
              data-focused={item.focused === '1' ? 'true' : 'false'}
              className={`rounded px-2 py-0.5 text-[11px] ${
                item.focused === '1' ? 'bg-white font-medium shadow-sm' : 'text-[#6b6b6b]'
              }`}
              onClick={() => void switchWindow(item)}
              disabled={busy}
            >
              {item.title || item.kind}
            </button>
          ))}
        </div>
      ) : null}
      <div
        className="relative min-h-0 flex-1 overflow-auto bg-[#f3f3f3]"
        data-testid="sandbox-web-stage"
        data-zoom={`${Math.round(zoom * 100)}%`}
        onWheel={onWheelZoom}
      >
        <div className="absolute right-2 top-2 z-10">
          <button
            type="button"
            data-testid="sandbox-screen-menu"
            aria-label="沙箱菜单"
            aria-expanded={chromeOpen}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/90 text-[#3d3d3d] shadow-sm hover:bg-white"
            onClick={() => setChromeOpen((value) => !value)}
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
          {chromeOpen ? (
            <div
              data-testid="sandbox-screen-menu-pop"
              className="absolute right-0 mt-1 w-56 rounded-lg border border-black/[0.08] bg-white p-2 text-left shadow-lg"
            >
              <p className="truncate px-1 text-[11px] text-[#8c8c8c]" title={pageUrl || undefined}>
                {pageTitle || '隔离网页'}
                {pageUrl ? ` · ${pageUrl}` : ''}
              </p>
              <p className="mt-1 px-1 text-[11px] text-[#6b6b6b]" data-testid="sandbox-web-copy">
                {humanCopy ||
                  (isOffice
                    ? '沙箱已用 LibreOffice 打开这份文档。这是字处理窗口，不是 PDF。'
                    : '请在此画面自行登录，不要在聊天里发送密码')}
              </p>
              <p className="mt-0.5 px-1 text-[10px] text-[#9a9a9a]" data-testid="sandbox-web-status">
                {status}
              </p>
              <button
                type="button"
                disabled={busy}
                className="mt-2 w-full rounded-md border border-black/[0.08] px-2.5 py-1.5 text-left text-[12px] disabled:opacity-50"
                onClick={() => void closeWindow()}
                data-testid="sandbox-close-keep-disk"
              >
                关闭窗口（文件保留）
              </button>
            </div>
          ) : null}
        </div>
        {focusedKind === 'files' && files.length > 0 ? (
          <div className="space-y-1 bg-white p-2" data-testid="sandbox-file-list">
            {files.map((file) => (
              <button
                key={file.name}
                type="button"
                data-testid={`sandbox-file-${file.name}`}
                className="block w-full rounded px-2 py-1.5 text-left text-[12px] hover:bg-[#f0f0f0]"
                onClick={() => {
                  void openPicoSandboxDocument({ filename: file.name });
                }}
              >
                {file.name}
              </button>
            ))}
          </div>
        ) : null}
        {imageUrl ? (
          <img
            ref={imgRef}
            src={imageUrl}
            alt="隔离浏览器画面"
            width={VIEWPORT_W}
            onClick={(ev) => void onViewportClick(ev)}
            style={{ width: `${Math.round(zoom * 100)}%` }}
            className="mx-auto block h-auto max-w-none cursor-crosshair bg-white"
            data-testid="sandbox-web-viewport"
          />
        ) : (
          <div
            className="flex min-h-[280px] items-center justify-center text-[13px] text-[#8c8c8c]"
            data-testid="sandbox-web-opening"
          >
            打开中
          </div>
        )}
      </div>
      {showLogin ? (
        <form
          className="space-y-1.5 border-t border-black/[0.06] px-2 py-2"
          data-testid="sandbox-login-form"
          onSubmit={(ev) => {
            ev.preventDefault();
            void sendVisible();
          }}
          autoComplete="off"
        >
          {hasTextInput ? (
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
          ) : null}
          {hasPasswordInput ? (
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
          ) : null}
          <div className="flex gap-1">
            {hasTextInput ? (
              <button
                type="submit"
                disabled={busy}
                className="rounded-md bg-[#1a1a1a] px-2.5 py-1 text-[11.5px] font-medium text-white disabled:opacity-50"
                data-testid="sandbox-web-send-text"
              >
                送可见字
              </button>
            ) : null}
            {hasPasswordInput ? (
              <button
                type="button"
                disabled={busy}
                className="rounded-md border border-black/[0.08] px-2.5 py-1 text-[11.5px] disabled:opacity-50"
                onClick={() => void sendSecret()}
                data-testid="sandbox-web-send-password"
              >
                送密码
              </button>
            ) : null}
          </div>
          {error ? (
            <p className="text-[11px] text-red-700" role="alert" data-testid="sandbox-web-error">
              {error}
            </p>
          ) : null}
        </form>
      ) : error ? (
        <p className="px-2 py-1 text-[11px] text-red-700" role="alert" data-testid="sandbox-web-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
