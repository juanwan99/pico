/**
 * Teacher-visible search sources from Pico gateway payloads.
 * Clickable links only — never invent URLs. Honest miss: 未检索到可用来源.
 */
import type { PicoRunEvent } from '~/data-provider/pico/api';
import {
  collectPicoSearchSources,
  type PicoSourceMessage,
} from '~/utils/picoSearchSources';

export default function PicoSearchSources({
  events,
  messages,
  onOpenSource,
}: {
  events?: PicoRunEvent[] | null;
  messages?: PicoSourceMessage[] | null;
  onOpenSource?: (url: string) => void;
}) {
  const view = collectPicoSearchSources(events, messages);
  if (!view.searched) {
    return null;
  }

  return (
    <section
      className="mb-3 rounded-lg border border-[#cfe0ff] bg-[#f5f9ff] px-3 py-2 dark:border-border-light dark:bg-surface-secondary"
      data-testid="pico-search-sources"
      aria-label="来源"
    >
      <p className="mb-1.5 text-[12px] font-semibold text-[#1a3a7a] dark:text-text-primary">来源</p>
      {view.sources.length === 0 ? (
        <p className="text-[12px] text-[#6b6b6b]" data-testid="pico-search-sources-miss">
          未检索到可用来源
        </p>
      ) : (
        <ul className="space-y-1">
          {view.sources.map((source) => (
            <li key={source.url} className="min-w-0">
              <a
                href={source.url}
                className="block truncate text-[12px] font-medium text-[#3b6fd9] underline-offset-2 hover:underline"
                data-testid="pico-search-source-link"
                title={source.title}
                onClick={(event) => {
                  if (!onOpenSource) {
                    return;
                  }
                  event.preventDefault();
                  onOpenSource(source.url);
                }}
              >
                {source.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
