import type { ReactNode } from 'react';
import SearchBar from '~/components/Nav/SearchBar';

/** Main /search pane. Search lives here so the stage is never a blank sheet. */
export default function SearchStage({ children }: { children?: ReactNode }) {
  return (
    <div
      className="flex h-full min-h-0 w-full flex-col bg-[color:var(--pico-shell)]"
      data-testid="search-stage"
    >
      <div className="mx-auto w-full max-w-[720px] shrink-0 px-6 pb-3 pt-8">
        <h1 className="pico-type-title text-[color:var(--pico-ink)]">搜索</h1>
        <p className="pico-type-body mt-1.5 text-[color:var(--pico-ink-2)]">在会话和消息里找</p>
        <div className="mt-4">
          <SearchBar autoFocus isStage />
        </div>
      </div>
      <div className="relative flex min-h-0 flex-1 flex-col">{children}</div>
    </div>
  );
}
