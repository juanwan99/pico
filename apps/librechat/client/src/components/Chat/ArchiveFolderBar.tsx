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

  return (
    <div className="mb-2 w-full text-left" data-testid="archive-folder-bar">
      <label className="pico-type-body flex items-center gap-2 text-[color:var(--pico-ink)]">
        存档位置
        <select
          className="pico-type-body h-9 min-w-0 flex-1 bg-transparent outline-none"
          value={folderId}
          data-testid="archive-folder-select"
          onChange={(e) => void pick(e.target.value)}
        >
          <option value="">我的文件</option>
          {folders.map((folder) =>
            folder.id ? (
              <option key={folder.id} value={folder.id}>
                {folder.name || folder.id}
              </option>
            ) : null,
          )}
        </select>
      </label>
      {error ? (
        <p className="pico-type-aux mt-0.5 text-[#b42318]" role="status">
          {error}
        </p>
      ) : null}
    </div>
  );
}
