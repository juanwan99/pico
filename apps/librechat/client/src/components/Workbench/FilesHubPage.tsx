/**
 * 我的文件 page. Directory actions live in the left rail + this panel.
 * Dialog does not transfer. No search-first school picker.
 */
import { useLocation } from 'react-router-dom';
import FilesDirectoryPanel from './FilesDirectoryPanel';
import WorkbenchShell from './WorkbenchShell';

export default function FilesHubPage() {
  const location = useLocation();
  const schoolView = location.hash === '#school';

  return (
    <WorkbenchShell
      title={schoolView ? '学校材料' : '我的文件'}
      subtitle={schoolView ? '在对话里按场文件夹勾选' : '本人做成的文件'}
      backTo="/c/new"
    >
      {schoolView ? (
        <div className="pico-type-body flex h-full items-start p-6 text-[color:var(--pico-ink-2)]">
          学校材料在对话里打开就是文件夹树。转存请到左侧「我的文件」目录。
        </div>
      ) : (
        <FilesDirectoryPanel className="h-full" />
      )}
    </WorkbenchShell>
  );
}
