/**
 * Chat archive location: default 我的文件 root. Pick a self-made folder.
 * School transfer is not here.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  getMyArchiveFolder,
  listMyFolders,
  putMyArchiveFolder,
  type PicoPersonalFolder,
} from '~/data-provider/pico/api';
import { folderLabelPath } from '~/utils/picoPersonalFolderTree';

export default function ArchiveFolderBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
  const [folderId, setFolderId] = useState('');
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [listed, archive] = await Promise.all([
        listMyFolders().catch(() => ({ folders: [] as PicoPersonalFolder[] })),
        getMyArchiveFolder(convo).catch(() => ({ folder_id: '', folder_name: '' })),
      ]);
      const next = Array.isArray(listed.folders) ? listed.folders : [];
      setFolders(next);
      const current = typeof archive.folder_id === 'string' ? archive.folder_id : '';
      setFolderId(next.some((row) => row.id === current) ? current : '');
    } catch {
      setError('存档夹现在列不出');
    }
  }, [convo]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const pick = useCallback(
    async (nextId: string) => {
      setFolderId(nextId);
      try {
        const row = await putMyArchiveFolder(convo, nextId);
        setFolderId(typeof row.folder_id === 'string' ? row.folder_id : nextId);
        setError(null);
      } catch {
        setError('存档夹没写上');
      }
    },
    [convo],
  );

  const currentName = folderId ? folderLabelPath(folders, folderId) : '我的文件';

  return (
    <div className="mb-2 w-full text-left" data-testid="archive-folder-bar">
      <label className="pico-type-body flex items-baseline gap-2 text-[color:var(--pico-ink)] dark:text-text-primary">
        存档位置
        <span className="relative min-w-0 flex-1">
          <select
            className="pico-type-body relative z-10 w-full cursor-pointer border-0 bg-transparent p-0 text-transparent shadow-none outline-none [appearance:none] [-moz-appearance:none] [-webkit-appearance:none]"
            value={folderId}
            data-testid="archive-folder-select"
            aria-label="存档位置"
            onChange={(e) => void pick(e.target.value)}
          >
            <option value="">我的文件</option>
            {folders.map((folder) =>
              folder.id ? (
                <option key={folder.id} value={folder.id}>
                  {folderLabelPath(folders, folder.id)}
                </option>
              ) : null,
            )}
          </select>
          <span className="pointer-events-none absolute inset-0 flex items-baseline gap-1 text-[color:var(--pico-ink-2)]">
            <span className="truncate">{currentName}</span>
            <span aria-hidden>▾</span>
          </span>
        </span>
      </label>
      {error ? (
        <p className="pico-type-aux mt-0.5 text-[#b42318]" role="status">
          {error}
        </p>
      ) : null}
    </div>
  );
}
