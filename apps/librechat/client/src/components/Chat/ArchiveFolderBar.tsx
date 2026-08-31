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

  return (
    <div className="mb-2 w-full text-left" data-testid="archive-folder-bar">
      <label className="pico-type-body flex items-center gap-2 text-[color:var(--pico-ink)]">
        <span className="shrink-0 text-[color:var(--pico-ink-2)]">存档位置</span>
        <span className="relative inline-flex min-w-0 flex-1">
          <select
            className="pico-type-body h-8 w-full max-w-full min-w-0 cursor-pointer appearance-none rounded-md border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] pl-2 pr-7 text-[color:var(--pico-ink)] shadow-sm outline-none hover:bg-[color:var(--pico-surface-2)]"
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
          <span
            aria-hidden
            className="pointer-events-none absolute inset-y-0 right-2 flex items-center text-[color:var(--pico-ink-3)]"
          >
            ▾
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
