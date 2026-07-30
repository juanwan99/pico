import { memo, useCallback, lazy, Suspense } from 'react';
import { useRecoilValue } from 'recoil';
import { SquarePen } from 'lucide-react';
import { QueryKeys } from 'librechat-data-provider';
import { useQueryClient } from '@tanstack/react-query';
import { Skeleton, Sidebar, Button, TooltipAnchor } from '@librechat/client';
import type { NavLink } from '~/common';
import { useShortcutAriaKey, useShortcutHint } from '~/hooks/useKeyboardShortcuts';
import { useActivePanel, resolveActivePanel, DEFAULT_PANEL } from '~/Providers';
import { CLOSE_SIDEBAR_ID } from '~/components/Chat/Menus/OpenSidebar';
import { useLocalize, useNewConvo } from '~/hooks';
import { clearMessagesCache, cn } from '~/utils';
import store from '~/store';

const AccountSettings = lazy(() => import('~/components/Nav/AccountSettings'));

const NewChatButton = memo(function NewChatButton({
  setActive,
}: {
  setActive: (id: string) => void;
}) {
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
          className="pico-wb-nav-item flex h-10 w-full items-center gap-2.5 rounded-xl bg-white px-2.5 text-sm font-medium text-text-primary shadow-sm ring-1 ring-black/[0.05] transition hover:bg-neutral-50 dark:bg-surface-tertiary dark:ring-white/10"
          onClick={handleClick}
        >
          <span className="flex size-7 shrink-0 items-center justify-center rounded-lg bg-neutral-900 text-white dark:bg-white dark:text-neutral-900">
            <SquarePen className="h-3.5 w-3.5" />
          </span>
          <span className="truncate">{localize('com_ui_new_chat')}</span>
        </a>
      }
    />
  );
});

const NavIconButton = memo(function NavIconButton({
  link,
  isActive,
  expanded,
  setActive,
  onExpand,
  onCollapse,
}: {
  link: NavLink;
  isActive: boolean;
  expanded: boolean;
  setActive: (id: string) => void;
  onExpand?: () => void;
  onCollapse?: () => void;
}) {
  const localize = useLocalize();

  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      if (link.onClick) {
        link.onClick(e);
        return;
      }
      if (isActive && expanded) {
        onCollapse?.();
        return;
      }
      if (!isActive) {
        setActive(link.id);
      }
      if (!expanded) {
        onExpand?.();
      }
    },
    [link, isActive, setActive, expanded, onExpand, onCollapse],
  );

  return (
    <TooltipAnchor
      description={localize(link.title)}
      side="right"
      render={
        <Button
          variant="ghost"
          aria-label={localize(link.title)}
          aria-pressed={isActive}
          data-testid={`nav-panel-${link.id}`}
          className={cn(
            'pico-wb-nav-item h-10 w-full justify-start gap-2.5 rounded-xl px-2.5 text-sm font-medium',
            isActive
              ? 'bg-white text-text-primary shadow-sm ring-1 ring-black/[0.05] dark:bg-surface-tertiary dark:ring-white/10'
              : 'text-text-secondary hover:bg-white/70 hover:text-text-primary dark:hover:bg-surface-hover',
          )}
          onClick={handleClick}
        >
          <link.icon className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span className="truncate">{localize(link.title)}</span>
        </Button>
      }
    />
  );
});

function ExpandedPanel({
  links,
  expanded = true,
  onCollapse,
  onExpand,
}: {
  links: NavLink[];
  expanded?: boolean;
  onCollapse?: () => void;
  onExpand?: () => void;
}) {
  const localize = useLocalize();
  const { active, setActive } = useActivePanel();
  const effectiveActive = resolveActivePanel(active, links);

  const toggleLabel = expanded ? 'com_nav_close_sidebar' : 'com_nav_open_sidebar';
  const toggleClick = expanded ? onCollapse : onExpand;
  const toggleSidebarHint = useShortcutHint('toggleSidebar', localize(toggleLabel));
  const toggleSidebarAriaKey = useShortcutAriaKey('toggleSidebar');

  return (
    <div className="pico-wb-rail flex h-full w-[11.5rem] flex-shrink-0 flex-col gap-1.5 border-r border-border-light bg-[#f3f4f6] px-2 py-2 dark:bg-surface-primary-alt">
      <TooltipAnchor
        side="right"
        description={toggleSidebarHint}
        render={
          <Button
            id={expanded ? CLOSE_SIDEBAR_ID : undefined}
            data-testid={expanded ? 'close-sidebar-button' : 'open-sidebar-button'}
            size="icon"
            variant="ghost"
            aria-label={localize(toggleLabel)}
            aria-expanded={expanded}
            aria-keyshortcuts={toggleSidebarAriaKey}
            className="h-9 w-9 rounded-lg"
            onClick={toggleClick}
          >
            <Sidebar aria-hidden="true" className="h-5 w-5 text-text-primary" />
          </Button>
        }
      />
      <NewChatButton setActive={setActive} />
      <div className="mx-2 border-b border-border-light" />
      <div className="flex flex-col gap-1 overflow-y-auto">
        {links.map((link) => (
          <NavIconButton
            key={link.id}
            link={link}
            isActive={link.id === effectiveActive}
            expanded={expanded ?? true}
            setActive={setActive}
            onExpand={onExpand}
            onCollapse={onCollapse}
          />
        ))}
      </div>

      <div className="mt-auto">
        <Suspense fallback={<Skeleton className="h-9 w-9 rounded-lg" />}>
          <AccountSettings collapsed />
        </Suspense>
      </div>
    </div>
  );
}

export default memo(ExpandedPanel);
