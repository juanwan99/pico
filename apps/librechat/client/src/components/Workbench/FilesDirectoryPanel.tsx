/**
 * Left file directory: personal folders + generated files.
 * Create folders and transfer to a writable school field via membership/land.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  createMyFolder,
  getPicoArtifactContent,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  transferMyArtifact,
  type EduSchoolField,
  type PicoArtifact,
  type PicoPersonalFolder,
} from '~/data-provider/pico/api';
import { cn } from '~/utils';

export default function FilesDirectoryPanel({ className }: { className?: string }) {
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
  const [folderId, setFolderId] = useState('');
  const [newFolderName, setNewFolderName] = useState('');
  const [mine, setMine] = useState<PicoArtifact[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
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

  const currentFolderName = useMemo(() => {
    if (!folderId) return '';
    return folders.find((row) => row.id === folderId)?.name || '';
  }, [folderId, folders]);

  const createFolder = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    setError(null);
    try {
      await createMyFolder(name);
      setNewFolderName('');
      await refresh();
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

  return (
    <div
      className={cn('flex min-h-0 flex-1 flex-col px-2.5 py-2', className)}
      data-testid="files-directory"
    >
      <p className="pico-type-sidebar pico-type-medium text-[color:var(--pico-ink)]">
        {currentFolderName ? currentFolderName : '我的文件'}
      </p>
      {folderId ? (
        <button
          type="button"
          className="pico-type-body mt-1 py-0.5 text-left text-[color:var(--pico-ink-2)]"
          onClick={() => setFolderId('')}
          data-testid="my-files-folder-up"
        >
          返回根目录
        </button>
      ) : (
        <form
          className="mt-2 flex gap-1"
          onSubmit={(event) => {
            event.preventDefault();
            void createFolder();
          }}
        >
          <input
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            placeholder="新夹名"
            className="pico-type-body h-9 min-w-0 flex-1 bg-transparent outline-none"
            data-testid="my-files-folder-name"
          />
          <button
            type="submit"
            className="pico-type-body h-9 shrink-0 text-[color:var(--pico-ink)]"
            data-testid="my-files-create-folder"
          >
            新建夹
          </button>
        </form>
      )}
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
            {!folderId
              ? folders.map((folder) => (
                  <button
                    key={folder.id}
                    type="button"
                    className="pico-type-body flex w-full items-center gap-1 py-1 text-left text-[color:var(--pico-ink)]"
                    onClick={() => setFolderId(folder.id)}
                    data-testid={`my-files-folder-${folder.id}`}
                  >
                    <span className="w-4 shrink-0 text-[color:var(--pico-ink-2)]">▸</span>
                    {folder.name || '未命名夹'}
                  </button>
                ))
              : null}
            {mine.length === 0 && (folderId || folders.length === 0) && !loading ? (
              <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有文件</p>
            ) : (
              mine.map((row) => {
                const name = row.user_label || row.title || '未命名';
                return (
                  <div
                    key={row.id}
                    className="py-1"
                    data-testid={`my-generated-${row.id}`}
                  >
                    <p className="pico-type-body truncate text-[color:var(--pico-ink)]">{name}</p>
                    <div className="mt-0.5 flex flex-wrap gap-2">
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
        <div className="mt-2 border-t border-[color:var(--pico-line)] pt-2" data-testid="my-files-transfer-dialog">
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
