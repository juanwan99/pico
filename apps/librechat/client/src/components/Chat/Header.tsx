import { memo } from 'react';
import { useRecoilValue } from 'recoil';
import { useMediaQuery } from '@librechat/client';
import { useGetStartupConfig } from '~/data-provider';
import ExportAndShareMenu from './ExportAndShareMenu';
import { OpenSidebar } from './Menus';
import store from '~/store';

function Header() {
  const { data: startupConfig } = useGetStartupConfig();
  const navVisible = useRecoilValue(store.sidebarExpanded);
  const isSmallScreen = useMediaQuery('(max-width: 768px)');

  return (
    <div className="via-presentation/70 md:from-presentation/80 md:via-presentation/50 2xl:from-presentation/0 absolute top-0 z-10 flex h-[52px] w-full items-center justify-between bg-gradient-to-b from-presentation to-transparent p-2 font-semibold text-text-primary 2xl:via-transparent">
      <div className="hide-scrollbar flex w-full items-center justify-between gap-2 overflow-x-auto">
        <div className="mx-1 flex items-center">{isSmallScreen ? <OpenSidebar /> : null}</div>
        {!(navVisible && isSmallScreen) ? (
          <div className="flex items-center gap-2">
            <ExportAndShareMenu
              isSharedButtonEnabled={startupConfig?.sharedLinksEnabled ?? false}
            />
          </div>
        ) : null}
      </div>
      <div />
    </div>
  );
}

const MemoizedHeader = memo(Header);
MemoizedHeader.displayName = 'Header';

export default MemoizedHeader;
