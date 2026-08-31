/**
 * Chat archive location: default 我的文件 root. Pick a self-made folder.
 * School transfer is not here.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getMyArchiveFolder,
  listMyFolders,
  putMyArchiveFolder,
  type PicoPersonalFolder,
} from '~/data-provider/pico/api';
import { folderLabelPath } from '~/utils/picoPersonalFolderTree';
import ComposerChromeRow from '~/components/Chat/ComposerChromeRow';

export default function ArchiveFolderBar({ conversationId }: { conversationId?: string | null }) {
  const convo = conversationId && conversationId !== 'new' ? conversationId : '';
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
  const [folderId, setFolderId] = useState('');
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

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

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      const target = event.target as Node | null;
      if (rootRef.current && target && !rootRef.current.contains(target)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false);
      }
    };
    document.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('keydown', onKeyDown);
    };
  }, [open]);

  const pick = useCallback(
    async (nextId: string) => {
      setFolderId(nextId);
      setOpen(false);
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

  const currentLabel = folderId ? folderLabelPath(folders, folderId) || '我的文件' : '我的文件';

  return (
    <div ref={rootRef} className="w-full text-left" data-testid="archive-folder-bar">
      <ComposerChromeRow label="存档位置">
        <button
          type="button"
          className="pico-type-body pico-chrome-control"
          data-testid="archive-folder-select"
          aria-label="存档位置"
          aria-expanded={open}
          aria-haspopup="listbox"
          onClick={() => setOpen((v) => !v)}
        >
          <span className="min-w-0 truncate">{currentLabel}</span>
          <span aria-hidden className="pico-type-aux pico-chrome-caret">
            ▾
          </span>
        </button>
      </ComposerChromeRow>
      {open ? (
        <ul
          className="mb-2 max-h-48 overflow-y-auto rounded-md border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] py-1"
          role="listbox"
          aria-label="存档位置"
          data-testid="archive-folder-list"
        >
          <li>
            <button
              type="button"
              role="option"
              aria-selected={folderId === ''}
              className="pico-type-body w-full px-2 py-1 text-left text-[color:var(--pico-ink)] hover:bg-[color:var(--pico-surface-2)]"
              onClick={() => void pick('')}
            >
              我的文件
            </button>
          </li>
          {folders.map((folder) =>
            folder.id ? (
              <li key={folder.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={folderId === folder.id}
                  className="pico-type-body w-full px-2 py-1 text-left text-[color:var(--pico-ink)] hover:bg-[color:var(--pico-surface-2)]"
                  data-testid={`archive-folder-option-${folder.id}`}
                  onClick={() => void pick(folder.id)}
                >
                  {folderLabelPath(folders, folder.id)}
                </button>
              </li>
            ) : null,
          )}
        </ul>
      ) : null}
      {error ? (
        <p className="pico-type-aux mt-0.5 text-[#b42318]" role="status">
          {error}
        </p>
      ) : null}
    </div>
  );
}
