import { memo } from 'react';
import { useRecoilValue } from 'recoil';
import { useMediaQuery } from '@librechat/client';
import { useGetStartupConfig } from '~/data-provider';
import { useChatContext } from '~/Providers';
import ExportAndShareMenu from './ExportAndShareMenu';
import ChatTitleEditor from './ChatTitleEditor';
import { OpenSidebar } from './Menus';
import store from '~/store';

function Header() {
  const { data: startupConfig } = useGetStartupConfig();
  const navVisible = useRecoilValue(store.sidebarExpanded);
  const isSmallScreen = useMediaQuery('(max-width: 768px)');
  const { conversation } = useChatContext();

  return (
    <div className="via-presentation/70 md:from-presentation/80 md:via-presentation/50 2xl:from-presentation/0 absolute top-0 z-10 flex h-[52px] w-full items-center justify-center bg-gradient-to-b from-presentation to-transparent font-semibold text-text-primary 2xl:via-transparent">
      <div
        className="hide-scrollbar flex h-full w-full max-w-[797px] items-center gap-2 overflow-x-auto px-2 sm:px-0"
        data-testid="chat-header-column"
      >
        <div className="flex shrink-0 items-center">{isSmallScreen ? <OpenSidebar /> : null}</div>
        <ChatTitleEditor
          conversationId={conversation?.conversationId}
          title={conversation?.title}
        />
        <div className="ml-auto flex shrink-0 items-center gap-2">
          {!(navVisible && isSmallScreen) ? (
            <ExportAndShareMenu
              isSharedButtonEnabled={startupConfig?.sharedLinksEnabled ?? false}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

const MemoizedHeader = memo(Header);
MemoizedHeader.displayName = 'Header';

export default MemoizedHeader;
