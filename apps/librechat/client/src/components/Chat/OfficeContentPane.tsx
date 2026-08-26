/**
 * Content-only office pages. No LibreOffice ribbon / browser chrome.
 */
import type { WheelEvent } from 'react';

export default function OfficeContentPane({
  title,
  pageUrls,
  pageIndex,
  onPage,
  zoom = 1,
  onWheel,
}: {
  title: string;
  pageUrls: string[];
  pageIndex: number;
  onPage: (index: number) => void;
  zoom?: number;
  onWheel?: (event: WheelEvent<HTMLDivElement>) => void;
}) {
  const total = pageUrls.length;
  const safeIndex = Math.min(Math.max(pageIndex, 0), Math.max(total - 1, 0));
  const src = pageUrls[safeIndex];
  return (
    <div
      className="flex min-h-0 flex-1 flex-col bg-[#111]"
      data-testid="office-content-pane"
      data-kind="office-pages"
    >
      {total > 1 ? (
        <div className="flex items-center justify-center gap-3 border-b border-white/10 px-3 py-1.5 text-[11px] text-[#c8c8c8]">
          <button
            type="button"
            data-testid="office-page-prev"
            className="disabled:opacity-40"
            disabled={safeIndex <= 0}
            onClick={() => onPage(safeIndex - 1)}
          >
            上一页
          </button>
          <span data-testid="office-page-label">
            {safeIndex + 1} / {total}
          </span>
          <button
            type="button"
            data-testid="office-page-next"
            className="disabled:opacity-40"
            disabled={safeIndex >= total - 1}
            onClick={() => onPage(safeIndex + 1)}
          >
            下一页
          </button>
        </div>
      ) : null}
      <div
        className="min-h-0 flex-1 overflow-auto"
        data-testid="office-content-stage"
        onWheel={onWheel}
      >
        {src ? (
          <img
            src={src}
            alt={title || '文档内容'}
            style={{ width: `${zoom * 100}%` }}
            className="mx-auto block h-auto max-w-none bg-transparent object-contain"
            data-testid="office-content-page"
          />
        ) : null}
      </div>
    </div>
  );
}
