/**
 * 我的文件 page. Directory actions live in the left rail + this panel.
 * Dialog does not transfer. No search-first school picker.
 */
import { useLocation } from 'react-router-dom';
import FilesDirectoryPanel from './FilesDirectoryPanel';
import SchoolFilesDirectory from './SchoolFilesDirectory';
import WorkbenchShell from './WorkbenchShell';

export default function FilesHubPage() {
  const location = useLocation();
  const schoolView = location.hash === '#school';

  return (
    <WorkbenchShell
      title={schoolView ? '学校文件' : '我的文件'}
      subtitle={schoolView ? '有权场里的材料' : '本人做成的文件'}
      backTo="/c/new"
    >
      {schoolView ? (
        <SchoolFilesDirectory className="h-full" />
      ) : (
        <FilesDirectoryPanel className="h-full" />
      )}
    </WorkbenchShell>
  );
}
