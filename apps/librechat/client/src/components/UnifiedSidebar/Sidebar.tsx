/**
 * Single-column workbench sidebar (WorkBuddy-class IA).
 * One rail only: nav + active panel content. No dual-column strip.
 */
import { memo, useCallback, lazy, Suspense } from 'react';
import { useRecoilValue } from 'recoil';
import { SquarePen, PanelLeftClose, PanelLeft } from 'lucide-react';
import { QueryKeys } from 'librechat-data-provider';
import { useQueryClient } from '@tanstack/react-query';
import { Skeleton, Button, TooltipAnchor } from '@librechat/client';
import type { NavLink } from '~/common';
import { useShortcutAriaKey, useShortcutHint } from '~/hooks/useKeyboardShortcuts';
import { useActivePanel, resolveActivePanel, DEFAULT_PANEL } from '~/Providers';
import { CLOSE_SIDEBAR_ID } from '~/components/Chat/Menus/OpenSidebar';
import SidePanelNav from '~/components/SidePanel/Nav';
import { useLocalize, useNewConvo } from '~/hooks';
import { clearMessagesCache, cn } from '~/utils';
import store from '~/store';

const AccountSettings = lazy(() => import('~/components/Nav/AccountSettings'));

function NewTaskButton({ setActive }: { setActive: (id: string) => void }) {
  const localize = useLocalize();
  const queryClient = useQueryClient();
  const { newConversation } = useNewConvo();
  const conversationId = useRecoilValue(store.conversationIdByIndex(0));
  const switchToHistory = useRecoilValue(store.newChatSwitchToHistory);
  const tooltipDescription = useShortcutHint('newChat', localize('com_ui_new_chat'));
  const ariaKey = useShortcutAriaKey('newChat');

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      if (e.button === 0 && !e.ctrlKey && !e.metaKey) {
        e.preventDefault();
        clearMessagesCache(queryClient, conversationId);
        queryClient.invalidateQueries([QueryKeys.messages]);
        newConversation();
        if (switchToHistory) {
          setActive(DEFAULT_PANEL);
        }
      }
    },
    [queryClient, conversationId, newConversation, switchToHistory, setActive],
  );

  return (
    <TooltipAnchor
      side="right"
      description={tooltipDescription}
      render={
        <a
          href="/c/new"
          data-testid="new-chat-button"
          aria-label={localize('com_ui_new_chat')}
          aria-keyshortcuts={ariaKey}
          className="flex h-10 w-full items-center gap-2.5 rounded-xl bg-neutral-900 px-3 text-sm font-medium text-white shadow-sm transition hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
          onClick={handleClick}
        >
          <SquarePen className="h-4 w-4 shrink-0" />
          <span className="truncate">{localize('com_ui_new_chat')}</span>
        </a>
      }
    />
  );
}

function Sidebar({
  links,
  expanded,
  onCollapse,
  onExpand,
  onResizeStart,
  onResizeKeyboard,
}: {
  links: NavLink[];
  expanded: boolean;
  onCollapse: () => void;
  onExpand: () => void;
  onResizeStart: (e: React.MouseEvent) => void;
  onResizeKeyboard: (direction: 'shrink' | 'grow') => void;
}) {
  const localize = useLocalize();
  const { active, setActive } = useActivePanel();
  const effectiveActive = resolveActivePanel(active, links);

  const toggleLabel = expanded ? 'com_nav_close_sidebar' : 'com_nav_open_sidebar';
  const toggleSidebarHint = useShortcutHint('toggleSidebar', localize(toggleLabel));
  const toggleSidebarAriaKey = useShortcutAriaKey('toggleSidebar');

  // Collapsed: icon-only strip (still single column)
  if (!expanded) {
    return (
      <div className="pico-wb-sidebar flex h-full w-full flex-col gap-1 bg-[#f3f4f6] px-1.5 py-2 dark:bg-surface-primary-alt">
        <TooltipAnchor
          side="right"
          description={toggleSidebarHint}
          render={
            <Button
              data-testid="open-sidebar-button"
              size="icon"
              variant="ghost"
              aria-label={localize(toggleLabel)}
              aria-expanded={false}
              aria-keyshortcuts={toggleSidebarAriaKey}
              className="h-9 w-9 rounded-lg"
              onClick={onExpand}
            >
              <PanelLeft className="h-5 w-5 text-text-primary" />
            </Button>
          }
        />
        <TooltipAnchor
          side="right"
          description={localize('com_ui_new_chat')}
          render={
            <a
              href="/c/new"
              data-testid="new-chat-button"
              aria-label={localize('com_ui_new_chat')}
              className="flex h-9 w-9 items-center justify-center rounded-lg bg-neutral-900 text-white dark:bg-white dark:text-neutral-900"
              onClick={(e) => {
                if (e.button === 0 && !e.ctrlKey && !e.metaKey) {
                  e.preventDefault();
                  onExpand();
                  setActive(DEFAULT_PANEL);
                }
              }}
            >
              <SquarePen className="h-4 w-4" />
            </a>
          }
        />
        <div className="mx-1 border-b border-border-light" />
        <div className="flex flex-1 flex-col gap-1 overflow-y-auto">
          {links.map((link) => (
            <TooltipAnchor
              key={link.id}
              side="right"
              description={localize(link.title)}
              render={
                <Button
                  size="icon"
                  variant="ghost"
                  aria-label={localize(link.title)}
                  aria-pressed={link.id === effectiveActive}
                  data-testid={`nav-panel-${link.id}`}
                  className={cn(
                    'h-9 w-9 rounded-lg',
                    link.id === effectiveActive
                      ? 'bg-white text-text-primary shadow-sm dark:bg-surface-tertiary'
                      : 'text-text-secondary',
                  )}
                  onClick={() => {
                    setActive(link.id);
                    onExpand();
                  }}
                >
                  <link.icon className="h-4 w-4" />
                </Button>
              }
            />
          ))}
        </div>
        <Suspense fallback={<Skeleton className="h-9 w-9 rounded-lg" />}>
          <AccountSettings collapsed />
        </Suspense>
      </div>
    );
  }

  // Expanded: ONE column — header nav + content panel
  return (
    <>
      <div className="pico-wb-sidebar flex h-full w-full min-w-0 flex-col bg-[#f3f4f6] dark:bg-surface-primary-alt">
        {/* Header: collapse + new task */}
        <div className="flex flex-col gap-2 border-b border-border-light/80 px-3 pb-3 pt-2">
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-semibold tracking-tight text-text-primary">Pico</span>
            <TooltipAnchor
              side="right"
              description={toggleSidebarHint}
              render={
                <Button
                  id={CLOSE_SIDEBAR_ID}
                  data-testid="close-sidebar-button"
                  size="icon"
                  variant="ghost"
                  aria-label={localize(toggleLabel)}
                  aria-expanded={true}
                  aria-keyshortcuts={toggleSidebarAriaKey}
                  className="h-8 w-8 rounded-lg"
                  onClick={onCollapse}
                >
                  <PanelLeftClose className="h-4 w-4 text-text-secondary" />
                </Button>
              }
            />
          </div>
          <NewTaskButton setActive={setActive} />
        </div>

        {/* Primary nav — horizontal scroll chips in same column */}
        <div
          className="flex gap-1 overflow-x-auto border-b border-border-light/80 px-2 py-2"
          role="tablist"
          aria-label={localize('com_nav_control_panel')}
        >
          {links.map((link) => {
            const isActive = link.id === effectiveActive;
            return (
              <button
                key={link.id}
                type="button"
                role="tab"
                aria-selected={isActive}
                data-testid={`nav-panel-${link.id}`}
                onClick={() => setActive(link.id)}
                className={cn(
                  'inline-flex shrink-0 items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-white text-text-primary shadow-sm ring-1 ring-black/[0.05] dark:bg-surface-tertiary dark:ring-white/10'
                    : 'text-text-secondary hover:bg-white/70 hover:text-text-primary dark:hover:bg-surface-hover',
                )}
              >
                <link.icon className="h-3.5 w-3.5 shrink-0" aria-hidden />
                <span className="max-w-[5.5rem] truncate">{localize(link.title)}</span>
              </button>
            );
          })}
        </div>

        {/* Active panel content — fills rest of single column */}
        <nav className="min-h-0 flex-1 overflow-hidden bg-[#f3f4f6] dark:bg-surface-primary-alt">
          <SidePanelNav links={links} />
        </nav>

        <div className="border-t border-border-light/80 px-2 py-2">
          <Suspense fallback={<Skeleton className="h-9 w-full rounded-lg" />}>
            <AccountSettings />
          </Suspense>
        </div>
      </div>

      {/* Resize handle */}
      <div
        role="separator"
        aria-orientation="vertical"
        aria-label={localize('com_ui_resize_sidebar')}
        tabIndex={0}
        className="absolute right-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-border-medium active:bg-border-heavy"
        onMouseDown={onResizeStart}
        onKeyDown={(e) => {
          if (e.key === 'ArrowLeft') {
            onResizeKeyboard('shrink');
          } else if (e.key === 'ArrowRight') {
            onResizeKeyboard('grow');
          }
        }}
      />
    </>
  );
}

export default memo(Sidebar);
