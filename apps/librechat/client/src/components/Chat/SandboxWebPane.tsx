/**
 * Result-panel isolated webpage. Browser windows stream JPEG frames pushed by
 * Chromium on repaint (#1215); office/files windows and a dropped stream fall
 * back to polling the PNG. Click → click_x/y, wheel → scroll, keys → Enter/Tab/…,
 * mouse drag → press / move / release (#1236: slider checks are the teacher's step).
 * Typing (#1265): a hidden textarea under the pane takes keys, IME and paste and
 * types straight into the page's focused field — account, password, 中文 alike.
 * Dead session: honest copy + reopen. Typed text is never logged.
 * Takeover (#1230): while the AI works the page the pane says「AI 正在操作 · 接管」;
 * 接管 stops the task and holds the page (the AI's hands are refused) until 交还 AI.
 * Hand back (#1238): the AI's turn ended on this page →「让 AI 接着做」(the caller's node).
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  destroyPicoSandboxSession,
  focusPicoSandboxWindow,
  getPicoSandboxScreenshot,
  getPicoSandboxSession,
  holdPicoSandboxSession,
  openPicoSandboxDocument,
  postPicoSandboxInput,
  streamPicoSandbox,
  type PicoSandboxWindow,
} from '~/data-provider/pico/api';
import { isOfficeFilename } from '~/utils/picoOpenInPane';

const POLL_MS = 400;
/** While frames stream, page meta (title / inputs) refreshes every Nth tick. */
const META_EVERY_TICKS = 5;
const STREAM_RETRY_MS = 5000;
const SCROLL_FLUSH_MS = 120;
/** A press that travels this far is a drag, not a click. */
const DRAG_START_PX = 4;
/** Fit the pane (#1224): the page lays out at the stage size once resizing settles. */
const FIT_SETTLE_MS = 300;
const FIT_MIN_DELTA_PX = 8;
const PANE_KEYS = new Set([
  'Enter',
  'Tab',
  'Backspace',
  'Delete',
  'Escape',
  'ArrowUp',
  'ArrowDown',
  'ArrowLeft',
  'ArrowRight',
  'PageUp',
  'PageDown',
  'Home',
  'End',
]);
/** Typed characters gather this long, then go to the page as one `text`. */
const TYPE_FLUSH_MS = 60;
const VIEWPORT_W = 1280;
const VIEWPORT_H = 800;

type PanePoint = { x: number; y: number };
type PaneDrag = {
  from: PanePoint;
  clientX: number;
  clientY: number;
  started: boolean;
  downSent: boolean;
  upSent: boolean;
  running: boolean;
  next: PanePoint | null;
  end: PanePoint | null;
};

export default function SandboxWebPane({
  sessionId,
  initialUrl,
  initialTitle,
  humanCopy,
  zoom = 1,
  onWheelZoom,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  kind,
  onDestroyed,
  onReopen,
  onOpenOfficeFile,
  aiBusy = false,
  onTakeOver,
  handBack,
}: {
  sessionId: string;
  initialUrl?: string;
  initialTitle?: string;
  humanCopy?: string;
  kind?: string;
  /** 1 = fit the pane width (fullscreen fills the stage, not a 390 strip). */
  zoom?: number;
  onWheelZoom?: (event: React.WheelEvent) => void;
  onZoomIn?: () => void;
  onZoomOut?: () => void;
  onZoomReset?: () => void;
  onDestroyed?: () => void;
  onReopen?: (args: { url: string; kind?: string }) => void;
  onOpenOfficeFile?: (filename: string) => void;
  /** The AI's turn is running (task bar shows 停止任务). */
  aiBusy?: boolean;
  /** 接管 also stops the task — same as the task bar's「停止任务」. */
  onTakeOver?: () => void;
  /** Shown while the page is idle and not held: the AI's last turn worked this page. */
  handBack?: React.ReactNode;
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
  const [chromeOpen, setChromeOpen] = useState(false);
  const [humanHold, setHumanHold] = useState(false);
  const [aiActing, setAiActing] = useState(false);
  const [holding, setHolding] = useState(false);
  const typeRef = useRef<HTMLTextAreaElement>(null);
  const [typeAt, setTypeAt] = useState<{ left: number; top: number } | null>(null);
  /** Pane input goes out in order: typed text before the key or click after it. */
  const inputChainRef = useRef<Promise<unknown>>(Promise.resolve());
  const typedRef = useRef({ text: '', timer: 0 });
  const composingRef = useRef(false);
  const objectUrlRef = useRef<string | null>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const liveRef = useRef(live);
  liveRef.current = live;
  const streamingRef = useRef(false);
  const scrollRef = useRef({ dy: 0, timer: 0 });
  const dragRef = useRef<PaneDrag | null>(null);
  const dragEndedRef = useRef(false);
  const stageRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef({ w: 0, h: 0 });

  const applyMeta = useCallback((meta: {
    url?: string;
    title?: string;
    windows?: PicoSandboxWindow[];
    kind?: string;
    files?: Array<{ name: string }>;
    human_hold?: boolean;
    ai_acting?: boolean;
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
    if (typeof meta.human_hold === 'boolean') {
      setHumanHold(meta.human_hold);
    }
    if (typeof meta.ai_acting === 'boolean') {
      setAiActing(meta.ai_acting);
    }
  }, []);

  const markDead = useCallback(() => {
    setLive('dead');
    setStatus('已关');
    setError(null);
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
    let ticks = 0;
    const id = window.setInterval(() => {
      if (cancelled || liveRef.current === 'dead') {
        return;
      }
      ticks += 1;
      if (streamingRef.current) {
        if (ticks % META_EVERY_TICKS === 0) {
          void refreshMeta();
        }
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

  useEffect(() => {
    const abort = new AbortController();
    let retry = 0;
    const run = async () => {
      try {
        await streamPicoSandbox(
          sessionId,
          (event) => {
            if (event.jpeg) {
              streamingRef.current = true;
              setImageUrl(`data:image/jpeg;base64,${event.jpeg}`);
              setLive('live');
            } else if (event.poll) {
              streamingRef.current = false;
            }
          },
          abort.signal,
        );
      } catch {
        /* fall back to polling below */
      }
      streamingRef.current = false;
      if (!abort.signal.aborted && liveRef.current !== 'dead') {
        retry = window.setTimeout(() => void run(), STREAM_RETRY_MS);
      }
    };
    void run();
    return () => {
      abort.abort();
      window.clearTimeout(retry);
      streamingRef.current = false;
    };
  }, [sessionId]);

  // The page lays out at the stage size instead of a 1280x800 picture shrunk in.
  // Zoomed in, the teacher wants the bigger picture: keep the last size.
  const fitsPane = live === 'live' && focusedKind === 'browser' && zoom === 1;
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !fitsPane || typeof ResizeObserver === 'undefined') {
      return;
    }
    let timer = 0;
    const send = () => {
      const w = Math.floor(stage.clientWidth);
      const h = Math.floor(stage.clientHeight);
      const last = fitRef.current;
      if (w <= 0 || h <= 0) {
        return;
      }
      if (Math.abs(w - last.w) < FIT_MIN_DELTA_PX && Math.abs(h - last.h) < FIT_MIN_DELTA_PX) {
        return;
      }
      fitRef.current = { w, h };
      void postPicoSandboxInput(sessionId, { viewport_width: w, viewport_height: h }).catch(() => {
        fitRef.current = last;
      });
    };
    const observer = new ResizeObserver(() => {
      window.clearTimeout(timer);
      timer = window.setTimeout(send, FIT_SETTLE_MS);
    });
    observer.observe(stage);
    return () => {
      observer.disconnect();
      window.clearTimeout(timer);
    };
  }, [fitsPane, sessionId]);

  const postInOrder = (body: { click_x?: number; click_y?: number; text?: string; key?: string }) => {
    const next = inputChainRef.current.then(() => postPicoSandboxInput(sessionId, body));
    inputChainRef.current = next.catch(() => undefined);
    return next;
  };

  const sendInput = async (body: { click_x?: number; click_y?: number; text?: string; key?: string }) => {
    setBusy(true);
    setError(null);
    try {
      const meta = await postInOrder(body);
      applyMeta(meta);
      if (!streamingRef.current) {
        await refreshShot();
      }
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

  const toPage = (clientX: number, clientY: number) => {
    const img = imgRef.current;
    const rect = img?.getBoundingClientRect();
    if (!img || !rect || rect.width <= 0 || rect.height <= 0) {
      return null;
    }
    const nw = img.naturalWidth || VIEWPORT_W;
    const nh = img.naturalHeight || VIEWPORT_H;
    return {
      x: Math.round((clientX - rect.left) * (nw / rect.width)),
      y: Math.round((clientY - rect.top) * (nh / rect.height)),
    };
  };

  const onViewportClick = async (ev: React.MouseEvent<HTMLImageElement>) => {
    if (dragEndedRef.current) {
      dragEndedRef.current = false;
      return;
    }
    const at = toPage(ev.clientX, ev.clientY);
    if (!at || live !== 'live') {
      return; // Not gated on busy: input is queued in order, a quick click after typing must land.
    }
    const stage = stageRef.current?.getBoundingClientRect();
    if (stage) {
      const el = stageRef.current;
      setTypeAt({
        left: ev.clientX - stage.left + (el?.scrollLeft || 0),
        top: ev.clientY - stage.top + (el?.scrollTop || 0),
      });
    }
    typeRef.current?.focus({ preventScroll: true });
    flushTyped();
    await sendInput({ click_x: at.x, click_y: at.y });
  };

  /** One request in flight; moves made meanwhile collapse to the latest point. */
  const pumpDrag = async (d: PaneDrag) => {
    if (d.running) {
      return;
    }
    d.running = true;
    try {
      for (;;) {
        if (!d.downSent) {
          d.downSent = true;
          await postPicoSandboxInput(sessionId, { drag: 'down', click_x: d.from.x, click_y: d.from.y });
        } else if (d.next) {
          const at = d.next;
          d.next = null;
          await postPicoSandboxInput(sessionId, { drag: 'move', click_x: at.x, click_y: at.y });
        } else if (d.end && !d.upSent) {
          d.upSent = true;
          applyMeta(
            await postPicoSandboxInput(sessionId, { drag: 'up', click_x: d.end.x, click_y: d.end.y }),
          );
          setStatus('已送进隔离浏览器');
        } else {
          break;
        }
      }
    } catch (err) {
      d.next = null;
      d.upSent = true;
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('404')) {
        markDead();
      } else {
        setError('拖动未送出，请重试');
      }
    } finally {
      d.running = false;
    }
  };

  const onViewportPointerDown = (ev: React.PointerEvent<HTMLImageElement>) => {
    dragEndedRef.current = false;
    const from = toPage(ev.clientX, ev.clientY);
    if (ev.button !== 0 || !from || busy || live !== 'live') {
      return;
    }
    dragRef.current = {
      from,
      clientX: ev.clientX,
      clientY: ev.clientY,
      started: false,
      downSent: false,
      upSent: false,
      running: false,
      next: null,
      end: null,
    };
    ev.currentTarget.setPointerCapture?.(ev.pointerId);
  };

  const onViewportPointerMove = (ev: React.PointerEvent<HTMLImageElement>) => {
    const d = dragRef.current;
    if (!d) {
      return;
    }
    if (!d.started) {
      if (Math.hypot(ev.clientX - d.clientX, ev.clientY - d.clientY) < DRAG_START_PX) {
        return;
      }
      d.started = true;
      setError(null);
    }
    d.next = toPage(ev.clientX, ev.clientY);
    void pumpDrag(d);
  };

  const onViewportPointerUp = (ev: React.PointerEvent<HTMLImageElement>) => {
    const d = dragRef.current;
    dragRef.current = null;
    if (!d?.started) {
      return;
    }
    dragEndedRef.current = ev.type === 'pointerup';
    d.end = toPage(ev.clientX, ev.clientY) || d.next || d.from;
    void pumpDrag(d);
  };

  const onViewportWheel = (ev: React.WheelEvent<HTMLImageElement>) => {
    // Ctrl/⌘ + wheel zooms the pane; a zoomed-in pane scrolls itself.
    if (ev.ctrlKey || ev.metaKey || zoom > 1 || live !== 'live') {
      return;
    }
    const pending = scrollRef.current;
    pending.dy += ev.deltaY;
    if (pending.timer) {
      return;
    }
    pending.timer = window.setTimeout(() => {
      const dy = Math.round(pending.dy);
      pending.dy = 0;
      pending.timer = 0;
      if (dy) {
        void postPicoSandboxInput(sessionId, { scroll_dy: dy }).catch(() => undefined);
      }
    }, SCROLL_FLUSH_MS);
  };

  const flushTyped = () => {
    const pending = typedRef.current;
    window.clearTimeout(pending.timer);
    pending.timer = 0;
    const text = pending.text;
    pending.text = '';
    if (text) {
      void sendInput({ text });
    }
  };

  const queueTyped = (text: string) => {
    if (!text || live !== 'live') {
      return;
    }
    const pending = typedRef.current;
    pending.text += text;
    window.clearTimeout(pending.timer);
    pending.timer = window.setTimeout(flushTyped, TYPE_FLUSH_MS);
  };

  const onTypeKey = (ev: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (live !== 'live' || composingRef.current || ev.nativeEvent.isComposing || ev.key === 'Process') {
      return;
    }
    const mod = ev.ctrlKey || ev.metaKey;
    if (mod && ev.key.toLowerCase() === 'a') {
      ev.preventDefault();
      flushTyped();
      void sendInput({ key: 'Control+a' });
      return;
    }
    if (mod || ev.altKey) {
      return; // Ctrl+V lands in onPaste; other shortcuts stay with this browser.
    }
    if (PANE_KEYS.has(ev.key)) {
      ev.preventDefault();
      flushTyped();
      void sendInput({ key: ev.key });
      return;
    }
    if (ev.key.length === 1) {
      ev.preventDefault();
      queueTyped(ev.key);
    }
  };

  const onTypeCompositionEnd = (ev: React.CompositionEvent<HTMLTextAreaElement>) => {
    composingRef.current = false;
    queueTyped(ev.data);
    ev.currentTarget.value = '';
  };

  const onTypePaste = (ev: React.ClipboardEvent<HTMLTextAreaElement>) => {
    ev.preventDefault();
    queueTyped(ev.clipboardData.getData('text'));
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

  const setHold = async (hold: boolean) => {
    setHolding(true);
    setError(null);
    try {
      if (hold) {
        onTakeOver?.();
      }
      applyMeta(await holdPicoSandboxSession(sessionId, hold));
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('404')) {
        markDead();
      } else {
        setError(hold ? '接管没成功，请再点一次' : '交还没成功，请再点一次');
      }
    } finally {
      setHolding(false);
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

  const takeover: 'ai' | 'human' | null =
    live !== 'live' ? null : humanHold ? 'human' : aiBusy && aiActing ? 'ai' : null;


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
      <div className="relative flex min-h-0 flex-1 flex-col">
        {takeover ? (
          <>
            <div
              className={`pointer-events-none absolute inset-0 z-[5] ring-2 ring-inset ${
                takeover === 'ai' ? 'ring-[#3b6fd9]/70' : 'ring-[#e0a100]/70'
              }`}
              aria-hidden
            />
            <div
              className="absolute left-1/2 top-2 z-20 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-[#1a1a1a]/90 py-1 pl-3 pr-1 text-[12px] text-white shadow-md"
              data-testid="sandbox-takeover-bar"
              data-state={takeover}
              role="status"
            >
              <span>{takeover === 'ai' ? 'AI 正在操作' : '你在操作 · AI 已停手'}</span>
              <button
                type="button"
                className="rounded-full bg-white px-2.5 py-0.5 text-[12px] font-medium text-[#1a1a1a] disabled:opacity-60"
                data-testid={takeover === 'ai' ? 'sandbox-takeover' : 'sandbox-handback'}
                disabled={holding}
                onClick={() => void setHold(takeover === 'ai')}
              >
                {takeover === 'ai' ? '接管' : '交还 AI'}
              </button>
            </div>
          </>
        ) : live === 'live' && !humanHold ? (
          handBack
        ) : null}
        <div
          ref={stageRef}
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
              <PicoIcon name="more" />
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
                      ? '沙箱内容框：只渲染页面/幻灯片，不是 Writer/Impress 整窗。'
                      : '点画面里的输入框直接打字登录；密码只进这个隔离网页，不要在聊天里发')}
                </p>
                <p className="mt-0.5 px-1 text-[10px] text-[#9a9a9a]" data-testid="sandbox-web-status">
                  {status}
                </p>
                {onZoomIn || onZoomOut ? (
                  <div className="mt-2 flex items-center gap-1 px-1" data-testid="sandbox-zoom-menu">
                    <button
                      type="button"
                      className="rounded-md p-1 hover:bg-black/[0.04]"
                      aria-label="缩小"
                      data-testid="pane-zoom-out"
                      onClick={onZoomOut}
                    >
                      <PicoIcon name="zoom-out" size="sm" />
                    </button>
                    <button
                      type="button"
                      className="pico-type-aux min-w-[2.5rem] rounded-md px-1 py-0.5 hover:bg-black/[0.04]"
                      aria-label="重置缩放"
                      data-testid="pane-zoom-label"
                      data-zoom={`${Math.round(zoom * 100)}%`}
                      onClick={onZoomReset}
                    >
                      {Math.round(zoom * 100)}%
                    </button>
                    <button
                      type="button"
                      className="rounded-md p-1 hover:bg-black/[0.04]"
                      aria-label="放大"
                      data-testid="pane-zoom-in"
                      onClick={onZoomIn}
                    >
                      <PicoIcon name="zoom-in" size="sm" />
                    </button>
                  </div>
                ) : null}
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
                    if (isOfficeFilename(file.name) && onOpenOfficeFile) {
                      onOpenOfficeFile(file.name);
                      return;
                    }
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
              onPointerDown={onViewportPointerDown}
              onPointerMove={onViewportPointerMove}
              onPointerUp={onViewportPointerUp}
              onPointerCancel={onViewportPointerUp}
              onDragStart={(ev) => ev.preventDefault()}
              draggable={false}
              onWheel={onViewportWheel}
              style={{ width: `${Math.round(zoom * 100)}%` }}
              className="mx-auto block h-auto max-w-none cursor-default bg-white"
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
          {live === 'live' ? (
            <textarea
              ref={typeRef}
              aria-label="在隔离网页里打字"
              autoComplete="off"
              autoCorrect="off"
              autoCapitalize="off"
              spellCheck={false}
              onKeyDown={onTypeKey}
              onCompositionStart={() => {
                composingRef.current = true;
              }}
              onCompositionEnd={onTypeCompositionEnd}
              onPaste={onTypePaste}
              onChange={(ev) => {
                // Text that arrives without a keydown (voice / mobile keyboards) still goes in.
                if (!composingRef.current) {
                  queueTyped(ev.currentTarget.value);
                  ev.currentTarget.value = '';
                }
              }}
              style={{ left: typeAt?.left ?? 0, top: typeAt?.top ?? 0 }}
              className="pointer-events-none absolute h-4 w-px resize-none overflow-hidden border-0 p-0 opacity-0"
              data-testid="sandbox-web-type"
            />
          ) : null}
        </div>
      </div>
      {error ? (
        <p className="px-2 py-1 text-[11px] text-red-700" role="alert" data-testid="sandbox-web-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
