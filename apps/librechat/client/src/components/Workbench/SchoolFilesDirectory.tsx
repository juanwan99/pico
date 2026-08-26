/**
 * Left/school directory: venue folder tree. Fields first; documents lazy on expand.
 * Avoids N× materials?field_id= fan-out that stalled the sidebar 2–3s+.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { EduSchoolField, EduSchoolMaterial } from '~/data-provider/pico/api';
import { PicoIcon } from '~/components/ui/pico-icons';
import {
  groupSchoolTree,
  loadSchoolFieldItems,
  loadSchoolFields,
} from '~/utils/picoSchoolTree';
import { cn } from '~/utils';

export default function SchoolFilesDirectory({ className }: { className?: string }) {
  const [fields, setFields] = useState<EduSchoolField[]>([]);
  const [itemsByField, setItemsByField] = useState<Record<string, EduSchoolMaterial[]>>({});
  const [loadedFields, setLoadedFields] = useState<Record<string, boolean>>({});
  const [loadingFields, setLoadingFields] = useState<Record<string, boolean>>({});
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const inflight = useRef<Record<string, Promise<void>>>({});

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      setBusy(true);
      setError(null);
      try {
        const row = await loadSchoolFields();
        if (cancelled) return;
        setFields(row.fields);
        if (row.configured === false) {
          setError('学校材料口还没接通');
        }
      } catch (err) {
        if (cancelled) return;
        const status = err instanceof Error ? err.message : String(err);
        setError(/\b403\b/.test(status) ? '无权看这份材料' : '学校文件现在列不出');
      } finally {
        if (!cancelled) setBusy(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const ensureFieldLoaded = useCallback(async (fieldId: string) => {
    if (!fieldId || fieldId === 'other') return;
    if (loadedFields[fieldId]) return;
    if (inflight.current[fieldId]) {
      await inflight.current[fieldId];
      return;
    }
    setLoadingFields((prev) => ({ ...prev, [fieldId]: true }));
    const task = (async () => {
      try {
        const row = await loadSchoolFieldItems(fieldId);
        setItemsByField((prev) => ({ ...prev, [fieldId]: row.items }));
        setLoadedFields((prev) => ({ ...prev, [fieldId]: true }));
        if (row.configured === false) {
          setError('学校材料口还没接通');
        }
      } catch {
        setItemsByField((prev) => ({ ...prev, [fieldId]: [] }));
        setLoadedFields((prev) => ({ ...prev, [fieldId]: true }));
      } finally {
        setLoadingFields((prev) => ({ ...prev, [fieldId]: false }));
        delete inflight.current[fieldId];
      }
    })();
    inflight.current[fieldId] = task;
    await task;
  }, [loadedFields]);

  const toggleField = useCallback(
    (fieldId: string) => {
      setExpanded((prev) => {
        const nextOpen = !prev[fieldId];
        if (nextOpen) {
          void ensureFieldLoaded(fieldId);
        }
        return { ...prev, [fieldId]: nextOpen };
      });
    },
    [ensureFieldLoaded],
  );

  const items = useMemo(() => Object.values(itemsByField).flat(), [itemsByField]);
  const groups = useMemo(() => groupSchoolTree(fields, items), [fields, items]);

  return (
    <div className={cn('flex min-h-0 flex-1 flex-col px-2.5 py-2', className)} data-testid="school-files-directory">
      <p className="pico-type-sidebar pico-type-medium text-[color:var(--pico-ink)]">学校材料</p>
      <div className="mt-2 min-h-0 flex-1 overflow-y-auto">
        {error ? (
          <p className="pico-type-body text-[#b42318]" role="status">
            {error}
          </p>
        ) : null}
        {busy && groups.length === 0 ? (
          <p className="pico-type-aux text-[color:var(--pico-ink-3)]">正在列出有权的场…</p>
        ) : null}
        {groups.map((group) => {
          const fieldKey = group.field.id || 'other';
          const isOpen = !!expanded[fieldKey];
          const isLoading = !!loadingFields[fieldKey];
          const hasLoaded = !!loadedFields[fieldKey] || fieldKey === 'other';
          return (
            <section key={fieldKey} className="py-0.5" data-testid={`school-dir-folder-${fieldKey}`}>
              <button
                type="button"
                className="pico-type-sidebar flex w-full items-center gap-1 py-0.5 text-left text-[color:var(--pico-ink)]"
                aria-expanded={isOpen}
                data-testid={`school-dir-folder-toggle-${fieldKey}`}
                onClick={() => toggleField(fieldKey)}
              >
                <span className="w-4 shrink-0 text-[color:var(--pico-ink-2)]">{isOpen ? '▾' : '▸'}</span>
                <PicoIcon
                  name={isOpen ? 'folder-open' : 'folder'}
                  size="sm"
                  className="shrink-0 text-[color:var(--pico-ink-2)]"
                />
                <span>{group.field.name || group.field.id}</span>
              </button>
              {isOpen ? (
                isLoading || !hasLoaded ? (
                  <p className="pico-type-aux py-0.5 pl-5 text-[color:var(--pico-ink-3)]">正在列出文档…</p>
                ) : group.items.length === 0 ? (
                  <p className="pico-type-aux py-0.5 pl-5 text-[color:var(--pico-ink-3)]">这场没有文档</p>
                ) : (
                  <ul className="pl-5">
                    {group.items.map((row) =>
                      row.id ? (
                        <li
                          key={row.id}
                          className="pico-type-body flex items-center gap-1 py-0.5 text-[color:var(--pico-ink)]"
                        >
                          <PicoIcon name="file" size="sm" className="shrink-0 text-[color:var(--pico-ink-2)]" />
                          <span className="min-w-0 truncate">{row.title || row.id}</span>
                        </li>
                      ) : null,
                    )}
                  </ul>
                )
              ) : null}
            </section>
          );
        })}
        {!busy && groups.length === 0 && !error ? (
          <p className="pico-type-body text-[color:var(--pico-ink-2)]">还没有有权的场</p>
        ) : null}
      </div>
    </div>
  );
}
