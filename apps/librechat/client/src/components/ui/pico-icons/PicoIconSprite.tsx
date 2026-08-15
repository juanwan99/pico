/**
 * Hidden SVG sprite for product chrome icons (edu-core linear family).
 * Mount once at app root inside .pico-app.
 *
 * CRITICAL: each <symbol> carries fill/stroke attrs. Parent CSS does NOT
 * inherit into <use> instances in Chromium/WebKit — without attrs icons
 * render as solid black blobs.
 */
export default function PicoIconSprite() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      xmlnsXlink="http://www.w3.org/1999/xlink"
      className="pico-icon-sprite"
      aria-hidden="true"
      focusable="false"
      width={0}
      height={0}
      style={{ position: 'absolute', width: 0, height: 0, overflow: 'hidden' }}
    >
      <symbol id="pico-i-home" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m3 10 9-7 9 7v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"  fill="none" />
              <path d="M9 21v-7h6v7"  fill="none" />
            </symbol>
      <symbol id="pico-i-grid" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="8" rx="2"  fill="none" />
              <rect x="14" y="3" width="7" height="5" rx="2"  fill="none" />
              <rect x="14" y="12" width="7" height="9" rx="2"  fill="none" />
              <rect x="3" y="15" width="7" height="6" rx="2"  fill="none" />
            </symbol>
      <symbol id="pico-i-apps" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="2"  fill="none" />
              <rect x="14" y="3" width="7" height="7" rx="2"  fill="none" />
              <rect x="3" y="14" width="7" height="7" rx="2"  fill="none" />
              <rect x="14" y="14" width="7" height="7" rx="2"  fill="none" />
            </symbol>
      <symbol id="pico-i-message" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M21 15a3 3 0 0 1-3 3H8l-5 3V6a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3Z"  fill="none" />
              <path d="M8 9h8M8 13h5"  fill="none" />
            </symbol>
      <symbol id="pico-i-file" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 3h8l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"  fill="none" />
              <path d="M14 3v5h5M8 13h7M8 17h5"  fill="none" />
            </symbol>
      <symbol id="pico-i-doc" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 3h8l4 4v14H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Z"  fill="none" />
              <path d="M14 3v5h5M8 13h7M8 17h5"  fill="none" />
            </symbol>
      <symbol id="pico-i-pen" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m15 5 4 4L8 20l-5 1 1-5Z"  fill="none" />
              <path d="m13 7 4 4"  fill="none" />
            </symbol>
      <symbol id="pico-i-chart" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 20V10M10 20V4M16 20v-7M22 20H2"  fill="none" />
              <path d="m3 7 6-4 6 6 6-5"  fill="none" />
            </symbol>
      <symbol id="pico-i-search" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7"  fill="none" />
              <path d="m20 20-4-4"  fill="none" />
            </symbol>
      <symbol id="pico-i-clock" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"  fill="none" />
              <path d="M12 7v5l3 2"  fill="none" />
            </symbol>
      <symbol id="pico-i-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"  fill="none" />
              <path d="m8 12 2.5 2.5L16 9"  fill="none" />
            </symbol>
      <symbol id="pico-i-plus" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 5v14M5 12h14"  fill="none" />
            </symbol>
      <symbol id="pico-i-folder" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 6h7l2 2h9v10a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-spark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m12 3 1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5Z"  fill="none" />
              <path d="m19 15 .8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-send" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m4 4 17 8-17 8 3-8Z"  fill="none" />
              <path d="M7 12h14"  fill="none" />
            </symbol>
      <symbol id="pico-i-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M5 12h14M14 7l5 5-5 5"  fill="none" />
            </symbol>
      <symbol id="pico-i-back" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M19 12H5M10 7l-5 5 5 5"  fill="none" />
            </symbol>
      <symbol id="pico-i-user" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="8" r="4"  fill="none" />
              <path d="M4 21a8 8 0 0 1 16 0"  fill="none" />
            </symbol>
      <symbol id="pico-i-logout" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3M16 17l5-5-5-5M21 12H9"  fill="none" />
            </symbol>
      <symbol id="pico-i-link" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1 1"  fill="none" />
              <path d="M14 11a5 5 0 0 0-7.5-.5l-2 2a5 5 0 0 0 7 7l1-1"  fill="none" />
            </symbol>
      <symbol id="pico-i-shield" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 3 4 6v5c0 5 3.2 8.5 8 10 4.8-1.5 8-5 8-10V6Z"  fill="none" />
              <path d="m9 12 2 2 4-4"  fill="none" />
            </symbol>
      <symbol id="pico-i-mic" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="9" y="3" width="6" height="11" rx="3"  fill="none" />
              <path d="M5 11a7 7 0 0 0 14 0M12 18v3"  fill="none" />
            </symbol>
      <symbol id="pico-i-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="m6 9 6 6 6-6"  fill="none" />
            </symbol>
      <symbol id="pico-i-plug" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 7v4M15 7v4M8 11h8v2a4 4 0 0 1-4 4h0a4 4 0 0 1-4-4Z"  fill="none" />
              <path d="M12 17v4"  fill="none" />
            </symbol>
      <symbol id="pico-i-bot" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="5" y="8" width="14" height="11" rx="3"  fill="none" />
              <path d="M12 3v5M9 13h.01M15 13h.01M9 17h6"  fill="none" />
            </symbol>
      <symbol id="pico-i-calendar" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="5" width="18" height="16" rx="3"  fill="none" />
              <path d="M8 3v4M16 3v4M3 10h18"  fill="none" />
            </symbol>
      <symbol id="pico-i-books" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M4 3h4v18H4zM10 5h4v16h-4zM16 4l4-1 3 17-4 1z"  fill="none" />
            </symbol>
      <symbol id="pico-i-more" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="5" cy="12" r="1.6"  fill="none" />
              <circle cx="12" cy="12" r="1.6"  fill="none" />
              <circle cx="19" cy="12" r="1.6"  fill="none" />
            </symbol>
      <symbol id="pico-i-mail" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="5" width="18" height="14" rx="3"  fill="none" />
              <path d="m4 7 8 6 8-6"  fill="none" />
            </symbol>
      <symbol id="pico-i-lightbulb" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 18h6M10 21h4"  fill="none" />
              <path d="M12 3a6 6 0 0 0-4 10.5c.8.7 1.2 1.5 1.2 2.5h5.6c0-1 .4-1.8 1.2-2.5A6 6 0 0 0 12 3Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-gift" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="8" width="18" height="4"  fill="none" />
              <path d="M5 12v8h14v-8M12 8v12"  fill="none" />
              <path d="M12 8s-1.5-5-4-5c-1.7 0-3 1.3-3 3s1.3 3 3 3h4ZM12 8s1.5-5 4-5c1.7 0 3 1.3 3 3s-1.3 3-3 3h-4Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-panel" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="3"  fill="none" />
              <path d="M9 4v16"  fill="none" />
            </symbol>
      <symbol id="pico-i-bell" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6"  fill="none" />
              <path d="M10 20a2 2 0 0 0 4 0"  fill="none" />
            </symbol>
      <symbol id="pico-i-help" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="12" r="9"  fill="none" />
              <path d="M9.5 9a2.5 2.5 0 0 1 4.9.8c0 1.7-2.4 2-2.4 3.7"  fill="none" />
              <path d="M12 17h.01"  fill="none" />
            </symbol>
      <symbol id="pico-i-zap" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M13 2 4 14h6l-1 8 9-12h-6Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-blocks" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="3" width="7" height="7" rx="2"  fill="none" />
              <rect x="14" y="3" width="7" height="7" rx="2"  fill="none" />
              <rect x="3" y="14" width="7" height="7" rx="2"  fill="none" />
              <rect x="14" y="14" width="7" height="7" rx="2"  fill="none" />
            </symbol>
      <symbol id="pico-i-folder-open" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M3 7h7l2 2h9v3"  fill="none" />
              <path d="m4 9-1 10a2 2 0 0 0 2 2h13l2-10H7Z"  fill="none" />
            </symbol>
      <symbol id="pico-i-arrow-up" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M12 19V5M6 11l6-6 6 6" fill="none" />
            </symbol>
      <symbol id="pico-i-close" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M6 6l12 12M18 6 6 18" fill="none" />
            </symbol>
      <symbol id="pico-i-zoom-in" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7" fill="none" />
              <path d="m20 20-4-4M11 8v6M8 11h6" fill="none" />
            </symbol>
      <symbol id="pico-i-zoom-out" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="11" cy="11" r="7" fill="none" />
              <path d="m20 20-4-4M8 11h6" fill="none" />
            </symbol>
      <symbol id="pico-i-maximize" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 4H4v5M15 4h5v5M4 15v5h5M20 15v5h-5" fill="none" />
            </symbol>
      <symbol id="pico-i-minimize" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M9 4H4v5M15 4h5v5M4 15v5h5M20 15v5h-5" fill="none" />
              <path d="M8 8h8v8H8z" fill="none" />
            </symbol>
      <symbol id="pico-i-refresh" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <path d="M20 12a8 8 0 1 1-2.3-5.6M20 5v5h-5" fill="none" />
            </symbol>
      <symbol id="pico-i-stop" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
              <rect x="7" y="7" width="10" height="10" rx="1.5" fill="none" />
            </symbol>
    </svg>
  );
}
