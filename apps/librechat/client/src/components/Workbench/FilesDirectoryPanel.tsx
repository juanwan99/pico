/**
 * 「我的文件」侧栏单树：展开层内首位「新建」、空夹可删。无中间大页、无「当前文件夹」二遍列表。
 */
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  createMyFolder,
  deleteMyFolder,
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
import { childrenOf } from '~/utils/picoPersonalFolderTree';
import { cn } from '~/utils';

export default function FilesDirectoryPanel({ className }: { className?: string }) {
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
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
      // Do not pull edu fields on every open — only when opening 转到学校.
      const [mineRow, folderRow] = await Promise.all([
        listMyPicoArtifacts().catch(() => ({ artifacts: [] as PicoArtifact[] })),
        listMyFolders().catch(() => ({ folders: [] as PicoPersonalFolder[] })),
      ]);
      setMine(Array.isArray(mineRow.artifacts) ? mineRow.artifacts : []);
      setFolders(Array.isArray(folderRow.folders) ? folderRow.folders : []);
    } catch (fetchError) {
      setError(fetchError instanceof Error ? fetchError.message : '文件目录现在列不出');
      setMine([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const openTransfer = useCallback(async (row: PicoArtifact) => {
    setTransferOf(row);
    setTransferMode('copy');
    setMessage(null);
    try {
      const fieldRow = await listEduFields().catch(() => ({ fields: [] as EduSchoolField[] }));
      const next = Array.isArray(fieldRow.fields) ? fieldRow.fields : [];
      setFields(next);
      setTransferField(next.find((field) => field.id)?.id || '');
    } catch {
      setFields([]);
      setTransferField('');
    }
  }, []);

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

  const filesByFolder = useMemo(() => {
    const map = new Map<string, PicoArtifact[]>();
    for (const row of mine) {
      const key = row.folder_id || '';
      const list = map.get(key) || [];
      list.push(row);
      map.set(key, list);
    }
    return map;
  }, [mine]);

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

  const createFolder = async (parentId: string) => {
    setError(null);
    try {
      const created = await createMyFolder('', parentId);
      const folder = created.folder;
      setExpanded((prev) => ({
        ...prev,
        root: true,
        ...(parentId ? { [parentId]: true } : {}),
      }));
      await refresh();
      if (folder?.id) {
        beginRename({
          id: folder.id,
          name: folder.name || '新建文件夹',
          parent_id: folder.parent_id || parentId,
        });
      }
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : '夹没建成');
    }
  };

  const removeFolder = async (folder: PicoPersonalFolder) => {
    setError(null);
    setMessage(null);
    try {
      await deleteMyFolder(folder.id);
      await refresh();
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : '夹没删掉');
    }
  };

  const isFolderEmpty = (folderId: string) => {
    if (childrenOf(folders, folderId).length > 0) return false;
    const files = filesByFolder.get(folderId) || [];
    return files.length === 0;
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

  const renderNewFolderRow = (parentId: string, depth: number) => (
    <div
      className="flex items-center gap-0.5 py-0.5"
      style={{ paddingLeft: `${depth * 12 + 16}px` }}
      data-testid={`my-files-new-under-${parentId || 'root'}`}
    >
      <button
        type="button"
        className="pico-type-body inline-flex min-w-0 flex-1 items-center gap-1 text-left text-[color:var(--pico-ink)]"
        onClick={() => void createFolder(parentId)}
        data-testid={parentId ? `my-files-create-folder-${parentId}` : 'my-files-create-folder'}
      >
        <PicoIcon name="plus" size="sm" className="shrink-0 text-[color:var(--pico-ink-2)]" />
        <span>新建文件夹</span>
      </button>
    </div>
  );

  const renderFiles = (parentId: string, depth: number) => {
    const rows = filesByFolder.get(parentId) || [];
    return rows.map((row) => {
      const name = row.user_label || row.title || '未命名';
      return (
        <div
          key={row.id}
          className="py-0.5"
          style={{ paddingLeft: `${depth * 12 + 16}px` }}
          data-testid={`my-generated-${row.id}`}
        >
          <div className="flex items-center gap-1">
            <PicoIcon name="file" size="sm" className="shrink-0 text-[color:var(--pico-ink-2)]" />
            <p className="pico-type-body min-w-0 flex-1 truncate text-[color:var(--pico-ink)]">{name}</p>
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
              onClick={() => void openTransfer(row)}
              data-testid={`my-files-transfer-${row.id}`}
            >
              转到学校
            </button>
          </div>
        </div>
      );
    });
  };

  const renderTreeNodes = (parentId: string, depth: number): ReactNode => {
    const rows = childrenOf(folders, parentId);
    return rows.map((folder) => {
      const kids = childrenOf(folders, folder.id);
      const files = filesByFolder.get(folder.id) || [];
      const hasBody = kids.length > 0 || files.length > 0;
      const isOpen = expanded[folder.id] === true;
      const empty = isFolderEmpty(folder.id);
      return (
        <div key={folder.id} data-testid={`my-files-tree-${folder.id}`}>
          <div
            className="flex items-center gap-0.5 py-0.5"
            style={{ paddingLeft: `${depth * 12}px` }}
          >
            <button
              type="button"
              className="flex h-5 w-4 shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]"
              aria-label={isOpen ? '收起' : '展开'}
              aria-expanded={isOpen}
              onClick={() =>
                setExpanded((prev) => ({ ...prev, [folder.id]: !isOpen }))
              }
              data-testid={`my-files-tree-toggle-${folder.id}`}
            >
              {isOpen ? '▾' : '▸'}
            </button>
            <PicoIcon
              name={isOpen ? 'folder-open' : 'folder'}
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
                onClick={() =>
                  setExpanded((prev) => ({ ...prev, [folder.id]: true }))
                }
              >
                {folder.name || '新建文件夹'}
              </button>
            )}
            {renamingId === folder.id ? null : (
              <>
                <button
                  type="button"
                  className="pico-type-aux shrink-0 text-[color:var(--pico-ink-2)]"
                  onClick={() => beginRename(folder)}
                  data-testid={`my-files-folder-rename-btn-${folder.id}`}
                >
                  重命名
                </button>
                <button
                  type="button"
                  className="pico-type-aux shrink-0 text-[color:var(--pico-ink-2)] disabled:opacity-40"
                  disabled={!empty}
                  title={empty ? '删除空夹' : '夹里还有内容，先清空再删'}
                  onClick={() => void removeFolder(folder)}
                  data-testid={`my-files-folder-delete-${folder.id}`}
                >
                  删除
                </button>
              </>
            )}
          </div>
          {isOpen ? (
            <>
              {renderNewFolderRow(folder.id, depth + 1)}
              {renderTreeNodes(folder.id, depth + 1)}
              {renderFiles(folder.id, depth + 1)}
              {!hasBody && !renamingId ? (
                <p
                  className="pico-type-aux py-0.5 text-[color:var(--pico-ink-3)]"
                  style={{ paddingLeft: `${(depth + 1) * 12 + 16}px` }}
                >
                  空文件夹
                </p>
              ) : null}
            </>
          ) : null}
        </div>
      );
    });
  };

  const rootOpen = expanded.root !== false;

  return (
    <div
      className={cn('flex min-h-0 flex-1 flex-col px-2.5 py-2', className)}
      data-testid="files-directory"
    >
      {error ? (
        <p className="pico-type-body text-[#b42318]" role="alert">
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="pico-type-body text-[color:var(--pico-ink-2)]" role="status">
          {message}
        </p>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto" data-testid="my-files-tree">
        {loading && mine.length === 0 && folders.length === 0 ? (
          <p className="pico-type-aux text-[color:var(--pico-ink-3)]">正在列出目录…</p>
        ) : (
          <>
            <div className="flex items-center gap-0.5 py-0.5">
              <button
                type="button"
                className="flex h-5 w-4 shrink-0 items-center justify-center text-[color:var(--pico-ink-2)]"
                aria-expanded={rootOpen}
                onClick={() =>
                  setExpanded((prev) => ({ ...prev, root: !(prev.root !== false) }))
                }
                data-testid="my-files-tree-toggle-root"
              >
                {rootOpen ? '▾' : '▸'}
              </button>
              <PicoIcon
                name={rootOpen ? 'folder-open' : 'folder'}
                size="sm"
                className="shrink-0 text-[color:var(--pico-ink-2)]"
              />
              <button
                type="button"
                className="pico-type-sidebar min-w-0 flex-1 truncate text-left text-[color:var(--pico-ink)]"
                data-testid="my-files-root"
                onClick={() => setExpanded((prev) => ({ ...prev, root: true }))}
              >
                我的文件
              </button>
            </div>
            {rootOpen ? (
              <>
                {renderNewFolderRow('', 1)}
                {renderTreeNodes('', 1)}
                {renderFiles('', 1)}
              </>
            ) : null}
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
