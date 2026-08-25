/**
 * 「我的文件」: personal folders + generated files. Transfer to school lives here.
 * Dialog does not pick a school venue.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { AlertCircle, Eye, FolderPlus, Loader2, RefreshCw, Search, X } from 'lucide-react';
import {
  createMyFolder,
  getPicoArtifactContent,
  listEduFields,
  listMyFolders,
  listMyPicoArtifacts,
  searchEduSchoolMaterials,
  transferMyArtifact,
  type EduSchoolField,
  type EduSchoolMaterial,
  type PicoArtifact,
  type PicoPersonalFolder,
} from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';
import { PicoIcon } from '~/components/ui/pico-icons';
import { cn } from '~/utils';

type FileGroup = 'all' | 'page' | 'material' | 'other';

const GROUP_LABELS: Record<FileGroup, string> = {
  all: '全部类型',
  page: '展示页',
  material: '资料',
  other: '其他',
};

function groupOf(row: EduSchoolMaterial): Exclude<FileGroup, 'all'> {
  if (row.kind === 'page') return 'page';
  if (row.kind === 'material') return 'material';
  return 'other';
}

function typeLabel(row: EduSchoolMaterial) {
  if (row.kind === 'page') {
    return row.publishState === 'published' ? '展示页' : '展示页灰稿';
  }
  if (row.kind === 'material') return '资料';
  return row.kind || '材料';
}

export default function FilesHubPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const schoolView = location.hash === '#school';
  const [rows, setRows] = useState<EduSchoolMaterial[]>([]);
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [folders, setFolders] = useState<PicoPersonalFolder[]>([]);
  const [folderId, setFolderId] = useState('');
  const [newFolderName, setNewFolderName] = useState('');
  const [mine, setMine] = useState<PicoArtifact[]>([]);
  const [mineBusy, setMineBusy] = useState<string | null>(null);
  const [mineError, setMineError] = useState<string | null>(null);
  const [minePreview, setMinePreview] = useState<{ title: string; html: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [schoolHint, setSchoolHint] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [group, setGroup] = useState<FileGroup>('all');
  const [transferOf, setTransferOf] = useState<PicoArtifact | null>(null);
  const [transferField, setTransferField] = useState('');
  const [transferMode, setTransferMode] = useState<'copy' | 'move'>('copy');
  const [transferBusy, setTransferBusy] = useState(false);
  const [transferMsg, setTransferMsg] = useState<string | null>(null);

  const refresh = useCallback(
    async (q = '') => {
      setLoading(true);
      setError(null);
      try {
        const [listed, fieldRow, mineRow, folderRow] = await Promise.all([
          searchEduSchoolMaterials(q.trim()).catch(() => ({
            configured: false,
            items: [] as EduSchoolMaterial[],
          })),
          listEduFields().catch(() => ({ fields: [] as EduSchoolField[] })),
          listMyPicoArtifacts(folderId).catch(() => ({ artifacts: [] as PicoArtifact[] })),
          listMyFolders().catch(() => ({ folders: [] as PicoPersonalFolder[] })),
        ]);
        const mineNext = Array.isArray(mineRow.artifacts) ? mineRow.artifacts : [];
        setMine(mineNext);
        setFolders(Array.isArray(folderRow.folders) ? folderRow.folders : []);
        setFields(Array.isArray(fieldRow.fields) ? fieldRow.fields : []);
        if (listed.configured === false) {
          setSchoolHint('学校材料口还没接通。对话里生成的文件在「我的文件」。');
          setError(null);
          setRows([]);
          setSelectedId(null);
          return;
        }
        setSchoolHint(null);
        const next = Array.isArray(listed.items) ? listed.items : [];
        setRows(next);
        setSelectedId((current) =>
          next.some((row) => row.id === current) ? current : (next[0]?.id ?? null),
        );
      } catch (fetchError) {
        const status = fetchError instanceof Error ? fetchError.message : String(fetchError);
        setError(/\b403\b/.test(status) ? '无权看这份材料' : '学校材料现在列不出');
        setRows([]);
        setSelectedId(null);
      } finally {
        setLoading(false);
      }
    },
    [folderId],
  );

  useEffect(() => {
    void refresh('');
  }, [refresh]);

  const fieldName = useCallback(
    (id?: string | null) => {
      if (!id) return '';
      return fields.find((field) => field.id === id)?.name || id;
    },
    [fields],
  );

  const currentFolderName = useMemo(() => {
    if (!folderId) return '';
    return folders.find((row) => row.id === folderId)?.name || '';
  }, [folderId, folders]);

  const filteredRows = useMemo(() => {
    const query = search.trim().toLocaleLowerCase();
    return rows.filter((row) => {
      const matchesGroup = group === 'all' || groupOf(row) === group;
      const matchesSearch =
        !query ||
        (row.title || '').toLocaleLowerCase().includes(query) ||
        fieldName(row.fieldId).toLocaleLowerCase().includes(query);
      return matchesGroup && matchesSearch;
    });
  }, [fieldName, group, rows, search]);

  useEffect(() => {
    if (filteredRows.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) =>
      filteredRows.some((row) => row.id === current) ? current : filteredRows[0].id,
    );
  }, [filteredRows]);

  const selected = useMemo(
    () => rows.find((row) => row.id === selectedId) ?? null,
    [rows, selectedId],
  );

  const openMine = async (row: PicoArtifact) => {
    setMineBusy(row.id);
    setMineError(null);
    try {
      const blob = await getPicoArtifactContent(row.id, false);
      const name = row.user_label || row.title || '生成物';
      if (/\.html?$/i.test(name) || /html/i.test(row.kind || '')) {
        const html = await blob.text();
        setMinePreview({ title: name, html });
        return;
      }
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = name;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (openError) {
      setMineError(openError instanceof Error ? openError.message : '打开失败');
    } finally {
      setMineBusy(null);
    }
  };

  const downloadMine = async (row: PicoArtifact) => {
    setMineBusy(row.id);
    setMineError(null);
    try {
      const blob = await getPicoArtifactContent(row.id, true);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = row.user_label || row.title || 'artifact.bin';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      setMineError(downloadError instanceof Error ? downloadError.message : '下载失败');
    } finally {
      setMineBusy(null);
    }
  };

  const createFolder = async () => {
    const name = newFolderName.trim();
    if (!name) return;
    setMineError(null);
    try {
      await createMyFolder(name);
      setNewFolderName('');
      await refresh('');
    } catch (createError) {
      setMineError(createError instanceof Error ? createError.message : '夹没建成');
    }
  };

  const runTransfer = async () => {
    if (!transferOf) return;
    setTransferBusy(true);
    setTransferMsg(null);
    try {
      const row = await transferMyArtifact(transferOf.id, transferField, transferMode);
      if (row.landed === true) {
        setTransferMsg(row.user_message || '已转到学校。刷新学校能看见。');
        setTransferOf(null);
        await refresh('');
      } else {
        setTransferMsg(row.user_message || row.error || '学校没写上。这份还留在我的文件。');
      }
    } catch (transferError) {
      setTransferMsg(transferError instanceof Error ? transferError.message : '学校这次没写成');
    } finally {
      setTransferBusy(false);
    }
  };

  const mineBlock = (
    <section className="flex-1 overflow-y-auto bg-[#fafafa] px-3 py-3" data-testid="my-generated-files">
      <p className="mb-1 text-[12px] font-medium text-[#333]">
        {currentFolderName ? `我的文件 / ${currentFolderName}` : '我的文件'}
      </p>
      <p className="mb-2 text-[11px] leading-4 text-[#8c8c8c]">
        对话生成物默认进根目录。转存到学校只在这页。
      </p>
      {folderId ? (
        <button
          type="button"
          className="mb-2 h-8 rounded-md border border-black/[0.08] px-2.5 text-[12px]"
          onClick={() => setFolderId('')}
          data-testid="my-files-folder-up"
        >
          返回根目录
        </button>
      ) : (
        <form
          className="mb-2 flex gap-1"
          onSubmit={(event) => {
            event.preventDefault();
            void createFolder();
          }}
        >
          <input
            value={newFolderName}
            onChange={(event) => setNewFolderName(event.target.value)}
            placeholder="新夹名"
            className="h-8 min-w-0 flex-1 rounded-md border border-black/[0.08] px-2 text-[12px] outline-none"
            data-testid="my-files-folder-name"
          />
          <button
            type="submit"
            className="inline-flex h-8 items-center gap-1 rounded-md border border-black/[0.08] px-2.5 text-[12px]"
            data-testid="my-files-create-folder"
          >
            <FolderPlus className="h-3.5 w-3.5" />
            新建夹
          </button>
        </form>
      )}
      {mineError ? (
        <p className="mb-2 text-[11px] text-red-700" role="alert">
          {mineError}
        </p>
      ) : null}
      {transferMsg ? (
        <p className="mb-2 text-[11px] text-[#555]" role="status">
          {transferMsg}
        </p>
      ) : null}
      {!folderId && folders.length > 0 ? (
        <ul className="mb-2 space-y-1.5" data-testid="my-files-folders">
          {folders.map((folder) => (
            <li key={folder.id}>
              <button
                type="button"
                className="flex w-full items-center gap-2 rounded-lg border border-black/[0.06] bg-white px-2.5 py-1.5 text-left"
                onClick={() => setFolderId(folder.id)}
                data-testid={`my-files-folder-${folder.id}`}
              >
                <PicoIcon name="folder-open" size="sm" />
                <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium">
                  {folder.name || '未命名夹'}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {loading && mine.length === 0 && folders.length === 0 ? (
        <div className="flex items-center justify-center gap-2 py-10 text-[12px] text-[#8c8c8c]">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载我的文件
        </div>
      ) : mine.length === 0 && (folderId || folders.length === 0) ? (
        <div className="flex flex-col items-center justify-center gap-1.5 py-10 text-[color:var(--pico-ink-3)]">
          <p className="text-[13px] font-medium text-[color:var(--pico-ink)]">还没有我的文件</p>
          <p className="max-w-xs text-center text-[11.5px] leading-4">
            对话里做成的文件会进这里。默认在根目录。
          </p>
        </div>
      ) : (
        <ul className="space-y-1.5">
          {mine.map((row) => {
            const name = row.user_label || row.title || '未命名';
            return (
              <li
                key={row.id}
                className="flex flex-wrap items-center gap-2 rounded-lg border border-black/[0.06] bg-white px-2.5 py-1.5"
                data-testid={`my-generated-${row.id}`}
              >
                <span className="min-w-0 flex-1 truncate text-[12.5px] font-medium">{name}</span>
                <button
                  type="button"
                  className="h-8 rounded-md border border-black/[0.08] px-2.5 text-[12px] disabled:opacity-50"
                  disabled={mineBusy !== null}
                  onClick={() => void openMine(row)}
                >
                  {mineBusy === row.id ? '打开中' : '打开'}
                </button>
                <button
                  type="button"
                  className="h-8 rounded-md bg-[#1a1a1a] px-2.5 text-[12px] font-semibold text-white disabled:opacity-50"
                  disabled={mineBusy !== null}
                  onClick={() => void downloadMine(row)}
                  data-testid={`my-generated-download-${row.id}`}
                >
                  下载
                </button>
                <button
                  type="button"
                  className="h-8 rounded-md border border-black/[0.08] px-2.5 text-[12px]"
                  onClick={() => {
                    setTransferOf(row);
                    setTransferField(fields[0]?.id || '');
                    setTransferMode('copy');
                    setTransferMsg(null);
                  }}
                  data-testid={`my-files-transfer-${row.id}`}
                >
                  转存到学校
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {transferOf ? (
        <div
          className="mt-3 rounded-lg border border-black/[0.08] bg-white p-3"
          data-testid="my-files-transfer-dialog"
        >
          <p className="mb-1 text-[12px] font-medium text-[#333]">
            转存「{transferOf.user_label || transferOf.title}」到学校
          </p>
          {fields.length === 0 ? (
            <p className="text-[11.5px] text-[#b42318]">没有可写的学校位置。没口不会假写入。</p>
          ) : (
            <>
              <label className="pico-type-aux mb-1 block text-[#555]">
                学校位置
                <select
                  className="mt-0.5 h-8 w-full rounded-md border border-black/[0.08] px-2"
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
              <div className="mb-2 flex gap-3 text-[12px]">
                <label className="inline-flex items-center gap-1">
                  <input
                    type="radio"
                    checked={transferMode === 'copy'}
                    onChange={() => setTransferMode('copy')}
                  />
                  复制
                </label>
                <label className="inline-flex items-center gap-1">
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
          <div className="flex gap-1">
            <button
              type="button"
              className="h-8 rounded-md bg-[#1a1a1a] px-2.5 text-[12px] font-semibold text-white disabled:opacity-50"
              disabled={transferBusy || !transferField}
              onClick={() => void runTransfer()}
              data-testid="my-files-transfer-confirm"
            >
              {transferBusy ? '转存中' : '转存'}
            </button>
            <button
              type="button"
              className="h-8 rounded-md border border-black/[0.08] px-2.5 text-[12px]"
              onClick={() => setTransferOf(null)}
            >
              取消
            </button>
          </div>
        </div>
      ) : null}
      {minePreview ? (
        <div
          className="mt-2 overflow-hidden rounded-lg border border-black/[0.08] bg-white"
          data-testid="my-generated-preview"
        >
          <div className="flex items-center gap-2 border-b border-black/[0.04] px-2.5 py-1">
            <p className="min-w-0 flex-1 truncate text-[11px] text-[#8c8c8c]">
              安全预览：{minePreview.title} · sandbox 禁用脚本与同源
            </p>
            <button
              type="button"
              className="h-7 rounded-md border border-black/[0.08] px-2 text-[11.5px]"
              onClick={() => setMinePreview(null)}
              data-testid="my-generated-preview-close"
            >
              关闭
            </button>
          </div>
          <iframe
            title={minePreview.title}
            sandbox=""
            referrerPolicy="no-referrer"
            srcDoc={minePreview.html}
            className="h-[420px] w-full border-0 bg-white"
            data-testid="my-generated-preview-iframe"
          />
        </div>
      ) : null}
    </section>
  );

  return (
    <WorkbenchShell
      title={schoolView ? '学校材料' : '我的文件'}
      subtitle={schoolView ? '学校场里的材料' : '本人做成的文件'}
      backTo="/c/new"
      actions={
        <button
          type="button"
          onClick={() => void refresh()}
          disabled={loading}
          className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-black/[0.08] px-2.5 text-[12px] text-[#555] hover:bg-black/[0.04] disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', loading && 'animate-spin')} />
          刷新
        </button>
      }
    >
      <div className="flex h-full min-h-[420px] flex-col">
        {schoolView ? (
          <>
            <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-black/[0.06] bg-white px-3 py-2">
              <label className="relative min-w-[220px] flex-1" htmlFor="school-file-search">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[#999]" />
                <input
                  id="school-file-search"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="搜索学校材料标题"
                  className="h-8 w-full rounded-md border border-black/[0.08] bg-[#f8f8f8] pl-8 pr-8 text-[12px] outline-none focus:border-black/20"
                />
                {search ? (
                  <button
                    type="button"
                    onClick={() => setSearch('')}
                    className="absolute right-1.5 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded text-[#999] hover:bg-black/[0.05]"
                    aria-label="清除搜索"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                ) : null}
              </label>
              <select
                value={group}
                onChange={(event) => setGroup(event.target.value as FileGroup)}
                className="h-8 rounded-md border border-black/[0.08] bg-white px-2.5 text-[12px] text-[#555] outline-none"
                aria-label="文件类型"
              >
                {(Object.keys(GROUP_LABELS) as FileGroup[]).map((key) => (
                  <option key={key} value={key}>
                    {GROUP_LABELS[key]}
                  </option>
                ))}
              </select>
              <span className="min-w-[64px] text-right text-[11px] text-[#999]">
                {filteredRows.length}/{rows.length} 个
              </span>
            </div>

            {schoolHint ? (
              <div
                role="status"
                className="m-3 rounded-lg border border-black/[0.08] bg-[#f7f7f7] px-3 py-2 text-[11.5px] text-[#555]"
              >
                {schoolHint}
              </div>
            ) : null}
            {error ? (
              <div
                role="alert"
                className="m-3 flex gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[11.5px] text-red-800"
              >
                <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>{error}</span>
              </div>
            ) : null}

            {loading && rows.length === 0 ? (
              <div className="flex flex-1 items-center justify-center gap-2 text-[12px] text-[#8c8c8c]">
                <Loader2 className="h-4 w-4 animate-spin" />
                加载学校材料
              </div>
            ) : rows.length === 0 && !error ? (
              <div className="flex flex-1 flex-col items-center justify-center gap-1.5 text-[color:var(--pico-ink-3)]">
                <div className="pico-icon-medallion mb-2 size-12">
                  <PicoIcon name="folder-open" size="lg" />
                </div>
                <p className="text-[13px] font-medium text-[color:var(--pico-ink)]">还没有学校材料</p>
                <p className="max-w-xs text-center text-[11.5px] leading-4">
                  学校场里暂时没有列出材料。生成物在「我的文件」，要从这页转存。
                </p>
                <button
                  type="button"
                  onClick={() => navigate('/more/files')}
                  className="pico-cta-accent mt-3 px-4 py-2 text-[12px] font-medium"
                >
                  去我的文件
                </button>
              </div>
            ) : (
              <div className="grid min-h-0 flex-1 md:grid-cols-[minmax(320px,42%)_minmax(0,1fr)]">
                <section className="min-h-0 overflow-y-auto border-r border-[color:var(--pico-line)] bg-[color:var(--pico-surface)]">
                  {filteredRows.length === 0 ? (
                    <div className="flex h-full min-h-48 flex-col items-center justify-center text-center">
                      <Search className="mb-2 h-6 w-6 text-[#bbb]" />
                      <p className="text-[12.5px] font-medium text-[#666]">没有匹配的学校材料</p>
                    </div>
                  ) : (
                    <ul className="divide-y divide-black/[0.05]">
                      {filteredRows.map((row) => {
                        const isSelected = row.id === selectedId;
                        return (
                          <li
                            key={row.id}
                            className={
                              isSelected
                                ? 'bg-[color:var(--pico-violet-wash)]'
                                : 'hover:bg-[color:var(--pico-surface-2)]'
                            }
                          >
                            <button
                              type="button"
                              onClick={() => setSelectedId(row.id)}
                              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left"
                              data-testid={`school-file-${row.id}`}
                            >
                              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-[color:var(--pico-violet-wash)] text-[color:var(--pico-violet-dark)]">
                                <PicoIcon name={row.kind === 'page' ? 'blocks' : 'doc'} size="sm" />
                              </span>
                              <span className="min-w-0 flex-1">
                                <span className="block truncate text-[12.5px] font-medium text-[color:var(--pico-ink)]">
                                  {row.title || '未命名'}
                                </span>
                                <span className="mt-0.5 block truncate text-[10.5px] text-[color:var(--pico-ink-2)]">
                                  {typeLabel(row)}
                                  {fieldName(row.fieldId) ? ` · ${fieldName(row.fieldId)}` : ''}
                                </span>
                              </span>
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </section>

                <section className="min-h-0 overflow-y-auto bg-[color:var(--pico-surface-2)]">
                  {selected ? (
                    <div className="flex min-h-full flex-col">
                      <div className="flex shrink-0 items-start gap-3 border-b border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] px-4 py-3">
                        <span className="pico-icon-medallion h-9 w-9 shrink-0">
                          <PicoIcon name={selected.kind === 'page' ? 'blocks' : 'doc'} size="sm" />
                        </span>
                        <div className="min-w-0 flex-1">
                          <h2 className="break-words text-[13px] font-semibold text-[color:var(--pico-ink)]">
                            {selected.title || '未命名'}
                          </h2>
                          <p className="mt-0.5 text-[10.5px] text-[#8c8c8c]">
                            {typeLabel(selected)}
                            {fieldName(selected.fieldId) ? ` · ${fieldName(selected.fieldId)}` : ''}
                          </p>
                        </div>
                      </div>
                      <div className="min-h-0 flex-1 p-3">
                        <div className="mb-2 flex items-center gap-1.5 text-[11px] font-medium text-[#666]">
                          <Eye className="h-3.5 w-3.5" />
                          摘要
                        </div>
                        <pre className="pico-panel max-h-[calc(100vh-190px)] overflow-auto whitespace-pre-wrap break-words p-3 font-mono text-[11.5px] leading-[1.65] text-[color:var(--pico-ink)]">
                          {selected.excerpt ? selected.excerpt : '（无摘要）'}
                        </pre>
                      </div>
                    </div>
                  ) : (
                    <div className="flex h-full min-h-48 items-center justify-center text-[12px] text-[#999]">
                      从左侧选择学校材料
                    </div>
                  )}
                </section>
              </div>
            )}
          </>
        ) : (
          mineBlock
        )}
      </div>
    </WorkbenchShell>
  );
}
