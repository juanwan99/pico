/**
 * Legacy /more/files route — redirect to chat and open sidebar rail.
 * Directory lives only in the left rail (no middle hub page).
 */
import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { setPicoSidebarRail } from '~/utils/picoSidebarRail';

export default function FilesHubPage() {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    setPicoSidebarRail(location.hash === '#school' ? 'school' : 'files');
    navigate('/c/new', { replace: true });
  }, [location.hash, navigate]);

  return (
    <div className="pico-type-body flex h-full items-center justify-center text-[color:var(--pico-ink-2)]">
      正在打开侧栏目录…
    </div>
  );
}
