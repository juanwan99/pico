import { useEffect, useState } from 'react';
import { deletePicoMemory, listPicoMemory, type PicoMemoryFile } from '~/data-provider/pico/api';

export default function MemoryStrip() {
  const [files, setFiles] = useState<PicoMemoryFile[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  const refresh = () => {
    void listPicoMemory()
      .then((payload) => setFiles(payload.files || []))
      .catch(() => setFiles([]));
  };

  useEffect(() => {
    refresh();
  }, []);

  const remove = (name: string) => {
    if (busy) {
      return;
    }
    setBusy(name);
    void deletePicoMemory(name)
      .then(() => refresh())
      .catch(() => undefined)
      .finally(() => setBusy(null));
  };

  return (
    <section className="mb-3" aria-label="跨窗记忆" data-testid="pico-memory-strip">
      <p className="mb-2 text-[12px] font-medium text-[#8c8c8c]">记忆</p>
      {files.length === 0 ? (
        <p className="rounded-lg bg-[#fafafa] px-3 py-2 text-[12px] text-[#8c8c8c] dark:bg-surface-tertiary">
          暂无跨窗短记
        </p>
      ) : (
        <ul className="space-y-1.5">
          {files.map((file) => (
            <li
              key={file.name}
              className="rounded-lg border border-black/[0.05] bg-[#fafafa] px-2.5 py-2 dark:border-border-light dark:bg-surface-tertiary"
            >
              <div className="flex items-start justify-between gap-2">
                <p className="truncate text-[12px] font-medium">{file.name}</p>
                <button
                  type="button"
                  data-testid="pico-memory-delete"
                  disabled={busy === file.name}
                  onClick={() => remove(file.name)}
                  className="shrink-0 text-[11px] text-[#8c8c8c] hover:text-[#c0392b] disabled:opacity-50"
                >
                  删除
                </button>
              </div>
              <p className="mt-0.5 line-clamp-3 whitespace-pre-wrap text-[11px] text-[#8c8c8c]">
                {file.text.trim() || '（空）'}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
