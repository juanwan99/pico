/**
 * 「我的文件」— Windows Explorer: folder icons, persistent tree, nested create/rename.
 * Transfer to school stays here; chat dialog does not transfer.
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  createMyFolder,
  getPicoArtifactContent,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  renameMyFolder,
  transferMyArtifact,
  type EduSchoolField,
  type PicoArtifact,
  type PicoPersonalFolder,
} from '~/data-provider/pico/api';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  childrenOf,
  folderPath,
} from '~/utils/picoPersonalFolderTree';
import { cn } from '~/utils';

export default function FilesDirectoryPanel({ className }: { className?: string }) {
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
  const [folderId, setFolderId] = useState('');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({ root: true });
  const [mine, setMine] = useState<PicoArtifact[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameDraft, setRenameDraft] = useState('');
  const renameInputRef = useRef<HTMLInputElement | null>(null);
  const [transferOf, setTransferOf] = useState<PicoArtifact | null>(null);
  const [transferField, setTransferField] = useState('');
  const [transferMode, setTransferMode] = useState<'copy' | 'move'>('copy');
  const [transferBusy, setTransferBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [mineRow, folderRow, fieldRow] = await Promise.all([
        listMyPicoArtifacts(folderId).catch(() => ({ artifacts: [] as PicoArtifact[] })),
        listMyFolders().catch(() => ({ folders: [] as PicoPersonalFolder[] })),
        listEduFields().catch(() => ({ fields: [] as EduSchoolField[] })),
      ]);
      setMine(Array.isArray(mineRow.artifacts) ? mineRow.artifacts : []);
      setFolders(Array.isArray(folderRow.folders) ? folderRow.folders : []);
      setFields(Array.isArray(fieldRow.fields) ? fieldRow.fields : []);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : '文件目录现在列不出');
      setMine([]);
    } finally {
      setLoading(false);
    }
  }, [folderId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!renamingId) return;
    const input = renameInputRef.current;
    if (!input) return;
    input.focus();
    input.select();
  }, [renamingId]);

  const breadcrumb = useMemo(() => folderPath(folders, folderId), [folders, folderId]);
  const childFolders = useMemo(() => childrenOf(folders, folderId), [folders, folderId]);

  const openFolder = (id: string) => {
    setFolderId(id);
    if (id) {
      setExpanded((prev) => ({ ...prev, root: true, [id]: true }));
      const chain = folderPath(folders, id);
      setExpanded((prev) => {
        const next = { ...prev, root: true };
        for (const row of chain) {
          next[row.id] = true;
        }
        return next;
      });
    }
  };

  const beginRename = (folder: PicoPersonalFolder) => {
    setRenamingId(folder.id);
    setRenameDraft(folder.name || '新建文件夹');
  };

  const commitRename = async () => {
    if (!renamingId) return;
    const name = renameDraft.trim() || '新建文件夹';
    const current = folders.find((row) => row.id === renamingId);
    setRenamingId(null);
    if (current && current.name === name) return;
    setError(null);
    try {
      await renameMyFolder(renamingId, name);
      await refresh();
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : '改名没写成');
      await refresh();
    }
  };

  const createFolder = async () => {
    setError(null);
    try {
      const created = await createMyFolder('', folderId);
      const folder = created.folder;
      if (folderId) {
        setExpanded((prev) => ({ ...prev, root: true, [folderId]: true }));
      } else {
        setExpanded((prev) => ({ ...prev, root: true }));
      }
      await refresh();
      if (folder?.id) {
        beginRename({ id: folder.id, name: folder.name || '新建文件夹', parent_id: folder.parent_id || folderId });
      }
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '夹没建成');
    }
  };

  const openMine = async (row: PicoArtifact) => {
    setBusyId(row.id);
    setError(null);
    try {
      const blob = await getPicoArtifactContent(row.id, true);
      const name = row.user_label || row.title || '生成物';
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (openError) {
      setError(openError instanceof Error ? openError.message : '打开失败');
    } finally {
      setBusyId(null);
    }
  };

  const runTransfer = async () => {
    if (!transferOf) return;
    setTransferBusy(true);
    setMessage(null);
    try {
      const row = await transferMyArtifact(transferOf.id, transferField, transferMode);
      if (row.landed === true) {
        setMessage(row.user_message || '已转到学校。刷新学校能看见。');
        setTransferOf(null);
        await refresh();
      } else {
        setMessage(row.user_message || row.error || '学校没写上。这份还留在我的文件。');
      }
    } catch (transferError) {
      setMessage(transferError instanceof Error ? transferError.message : '学校这次没写成');
    } finally {
      setTransferBusy(false);
    }
  };

  const renderRenameInput = (folder: PicoPersonalFolder) => (
    <input
      ref={renameInputRef}
      value={renameDraft}
      data-testid={`my-files-folder-rename-${folder.id}`}
      className="pico-type-body min-w-0 flex-1 border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-1 py-0.5 outline-none"
      onChange={(event) => setRenameDraft(event.target.value)}
      onBlur={() => void commitRename()}
      onKeyDown={(event) => {
        if (event.key === 'Enter') {
          event.preventDefault();
          void commitRename();
        }
        if (event.key === 'Escape') {
          event.preventDefault();
          setRenamingId(null);
        }
      }}
    />
  );

  const renderTreeNodes = (parentId: string, depth: number): ReactNode => {
    const rows = childrenOf(folders, parentId);
    return rows.map((folder) => {
      const kids = childrenOf(folders, folder.id);
      const hasKids = kids.length > 0;
      const isOpen = expanded[folder.id] === true;
      const selected = folderId === folder.id;
      return (
        <div key={folder.id} data-testid={`my-files-tree-${folder.id}`}>
          <div
            className={cn(
              'flex items-center gap-0.5 py-0.5',
              selected ? 'bg-[color:var(--pico-surface-2,transparent)]' : '',
            )}
            style={{ paddingLeft: `${depth * 12}px` }}
          >
            <button
              type="button"
              className="flex h-5 w-4 shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]"
              aria-label={isOpen ? '收起' : '展开'}
              aria-expanded={hasKids ? isOpen : undefined}
              disabled={!hasKids}
              onClick={() =>
                setExpanded((prev) => ({ ...prev, [folder.id]: !isOpen }))
              }
              data-testid={`my-files-tree-toggle-${folder.id}`}
            >
              {hasKids ? (isOpen ? '▾' : '▸') : <span className="inline-block w-2" />}
            </button>
            <PicoIcon
              name={selected || isOpen ? 'folder-open' : 'folder'}
              size="sm"
              className="shrink-0 text-[color:var(--pico-ink-2)]"
            />
            {renamingId === folder.id ? (
              renderRenameInput(folder)
            ) : (
              <button
                type="button"
                className="pico-type-body min-w-0 flex-1 truncate text-left text-[color:var(--pico-ink)]"
                data-testid={`my-files-folder-${folder.id}`}
                onClick={() => openFolder(folder.id)}
                onDoubleClick={() => openFolder(folder.id)}
              >
                {folder.name || '新建文件夹'}
              </button>
            )}
            {renamingId === folder.id ? null : (
              <button
                type="button"
                className="pico-type-aux shrink-0 text-[color:var(--pico-ink-2)]"
                onClick={() => beginRename(folder)}
                data-testid={`my-files-folder-rename-btn-${folder.id}`}
              >
                重命名
              </button>
            )}
          </div>
          {hasKids && isOpen ? renderTreeNodes(folder.id, depth + 1) : null}
        </div>
      );
    });
  };

  return (
    <div
      className={cn('flex min-h-0 flex-1 flex-col px-2.5 py-2', className)}
      data-testid="files-directory"
    >
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        <button
          type="button"
          className="pico-type-sidebar inline-flex min-w-0 items-center gap-1 text-[color:var(--pico-ink-2)]"
          onClick={() => openFolder('')}
          data-testid="my-files-root"
        >
          <PicoIcon name={folderId ? 'folder' : 'folder-open'} size="sm" />
          <span>我的文件</span>
        </button>
        {breadcrumb.map((row) => (
          <span key={row.id} className="inline-flex min-w-0 items-center gap-1">
            <span className="pico-type-aux text-[color:var(--pico-ink-3)]">/</span>
            <button
              type="button"
              className="pico-type-sidebar truncate text-[color:var(--pico-ink)]"
              onClick={() => openFolder(row.id)}
            >
              {row.name || '新建文件夹'}
            </button>
          </span>
        ))}
      </div>

      <button
        type="button"
        className="pico-type-body mt-2 self-start text-[color:var(--pico-ink)]"
        onClick={() => void createFolder()}
        data-testid="my-files-create-folder"
      >
        新建文件夹
      </button>

      {error ? (
        <p className="pico-type-body mt-1 text-[#b42318]" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="pico-type-body mt-1 text-[color:var(--pico-ink-2)]" role="status">
          {message}
        </p>
      ) : null}

      <div className="mt-2 min-h-0 flex-1 overflow-y-auto" data-testid="my-generated-files">
        {loading && mine.length === 0 && folders.length === 0 ? (
          <p className="pico-type-aux text-[color:var(--pico-ink-3)]">正在列出目录…</p>
        ) : (
          <>
            <div data-testid="my-files-tree" className="mb-2 border-b border-[color:var(--pico-line)] pb-2">
              <div className="flex items-center gap-0.5 py-0.5">
                <button
                  type="button"
                  className="flex h-5 w-4 shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]"
                  aria-expanded={expanded.root !== false}
                  onClick={() =>
                    setExpanded((prev) => ({ ...prev, root: !(prev.root !== false) }))
                  }
                  data-testid="my-files-tree-toggle-root"
                >
                  {expanded.root !== false ? '▾' : '▸'}
                </button>
                <PicoIcon
                  name={folderId ? 'folder' : 'folder-open'}
                  size="sm"
                  className="shrink-0 text-[color:var(--pico-ink-2)]"
                />
                <button
                  type="button"
                  className={cn(
                    'pico-type-sidebar min-w-0 flex-1 truncate text-left',
                    folderId ? 'text-[color:var(--pico-ink-2)]' : 'text-[color:var(--pico-ink)]',
                  )}
                  onClick={() => openFolder('')}
                >
                  我的文件
                </button>
              </div>
              {expanded.root !== false ? renderTreeNodes('', 1) : null}
            </div>

            <p className="pico-type-aux mb-1 text-[color:var(--pico-ink-3)]">当前文件夹</p>
            {childFolders.map((folder) => (
              <div
                key={`content-${folder.id}`}
                className="flex items-center gap-1 py-1"
                data-testid={`my-files-content-folder-${folder.id}`}
              >
                <PicoIcon name="folder" size="sm" className="shrink-0 text-[color:var(--pico-ink-2)]" />
                <button
                  type="button"
                  className="pico-type-body min-w-0 flex-1 truncate text-left text-[color:var(--pico-ink)]"
                  onClick={() => openFolder(folder.id)}
                  onDoubleClick={() => openFolder(folder.id)}
                >
                  {folder.name || '新建文件夹'}
                </button>
              </div>
            ))}

            {mine.length === 0 && childFolders.length === 0 && !loading && !renamingId ? (
              <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有文件</p>
            ) : (
              mine.map((row) => {
                const name = row.user_label || row.title || '未命名';
                return (
                  <div key={row.id} className="py-1" data-testid={`my-generated-${row.id}`}>
                    <div className="flex items-center gap-1">
                      <PicoIcon name="file" size="sm" className="shrink-0 text-[color:var(--pico-ink-2)]" />
                      <p className="pico-type-body min-w-0 flex-1 truncate text-[color:var(--pico-ink)]">
                        {name}
                      </p>
                    </div>
                    <div className="mt-0.5 flex flex-wrap gap-2 pl-5">
                      <button
                        type="button"
                        className="pico-type-body text-[color:var(--pico-ink-2)]"
                        disabled={busyId !== null}
                        onClick={() => void openMine(row)}
                      >
                        打开
                      </button>
                      <button
                        type="button"
                        className="pico-type-body text-[color:var(--pico-ink-2)]"
                        onClick={() => {
                          setTransferOf(row);
                          setTransferField(fields[0]?.id || '');
                          setTransferMode('copy');
                          setMessage(null);
                        }}
                        data-testid={`my-files-transfer-${row.id}`}
                      >
                        转到学校
                      </button>
                    </div>
                  </div>
                );
              })
            )}
          </>
        )}
      </div>

      {transferOf ? (
        <div
          className="mt-2 border-t border-[color:var(--pico-line)] pt-2"
          data-testid="my-files-transfer-dialog"
        >
          <p className="pico-type-body text-[color:var(--pico-ink)]">
            转到学校 · {transferOf.user_label || transferOf.title}
          </p>
          {fields.length === 0 ? (
            <p className="pico-type-body mt-1 text-[#b42318]">没有可写的学校位置。没口不会假写入。</p>
          ) : (
            <>
              <label className="pico-type-body mt-1 block text-[color:var(--pico-ink)]">
                学校位置
                <select
                  className="pico-type-body mt-1 h-9 w-full bg-transparent outline-none"
                  value={transferField}
                  onChange={(event) => setTransferField(event.target.value)}
                  data-testid="my-files-transfer-field"
                >
                  {fields.map((field) =>
                    field.id ? (
                      <option key={field.id} value={field.id}>
                        {field.name || field.id}
                      </option>
                    ) : null,
                  )}
                </select>
              </label>
              <div className="mt-1 flex gap-3">
                <label className="pico-type-body inline-flex items-center gap-1">
                  <input
                    type="radio"
                    checked={transferMode === 'copy'}
                    onChange={() => setTransferMode('copy')}
                  />
                  复制
                </label>
                <label className="pico-type-body inline-flex items-center gap-1">
                  <input
                    type="radio"
                    checked={transferMode === 'move'}
                    onChange={() => setTransferMode('move')}
                  />
                  移动
                </label>
              </div>
            </>
          )}
          <div className="mt-2 flex gap-3">
            <button
              type="button"
              className="pico-type-body text-[color:var(--pico-ink)] disabled:opacity-50"
              disabled={transferBusy || !transferField}
              onClick={() => void runTransfer()}
              data-testid="my-files-transfer-confirm"
            >
              {transferBusy ? '转存中' : '转存'}
            </button>
            <button
              type="button"
              className="pico-type-body text-[color:var(--pico-ink-2)]"
              onClick={() => setTransferOf(null)}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
