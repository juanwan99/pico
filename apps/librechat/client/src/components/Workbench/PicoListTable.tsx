import { useMemo, useState, type ReactNode } from 'react';
import * as Popover from '@radix-ui/react-popover';
import { DataTableV2, type TableColumn } from '@librechat/client';
import { ListFilter } from 'lucide-react';

type Filter<Row> = { label: string; value: (row: Row) => string };

export default function PicoListTable<Row extends Record<string, unknown>>({
  data,
  columns,
  filters,
  emptyState,
}: {
  data: Row[];
  columns: TableColumn<Row, unknown>[];
  filters: Filter<Row>[];
  emptyState: ReactNode;
}) {
  const [selected, setSelected] = useState<Record<string, string[]>>({});
  const choices = useMemo(() => filters.map(({ label, value }) => ({
    label,
    values: [...new Set([...data.map(value), ...(selected[label] ?? [])])].sort((a, b) =>
      a.localeCompare(b, 'zh-CN'),
    ),
  })), [data, filters, selected]);
  const visibleRows = useMemo(() => data.filter((row) => filters.every(({ label, value }) => {
    const values = selected[label];
    return !values?.length || values.includes(value(row));
  })), [data, filters, selected]);
  const tableColumns = useMemo(() => columns.map((column) => ({
    sortDescFirst: false,
    sortUndefined: 'last' as const,
    ...column,
  })), [columns]);

  function toggle(label: string, value: string) {
    setSelected((current) => {
      const values = current[label] ?? [];
      const next = values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
      return { ...current, [label]: next };
    });
  }

  const active = Object.values(selected).some((values) => values.length > 0);
  const clear = (
    <button type="button" className="text-text-secondary underline" onClick={() => setSelected({})}>
      清除筛选
    </button>
  );

  return (
    <DataTableV2
      columns={tableColumns}
      data={visibleRows}
      manualSorting={false}
      className="h-auto max-h-[32rem] [&_table]:min-w-[36rem] [&_table]:text-[13px] [&_th]:h-auto [&_td]:py-1 [&_tbody_tr]:border-b [&_tbody_tr]:border-solid [&_tbody_tr]:border-border-light"
      config={{ selection: { enableRowSelection: false }, search: { enableSearch: false } }}
      emptyState={(
        <div className="px-4 py-6 text-center text-[13px] text-text-secondary">
          {active ? <><p role="status">暂无符合筛选的记录</p>{clear}</> : emptyState}
        </div>
      )}
      customActionsRenderer={() => (
        <div className="flex flex-wrap items-center gap-2 p-2 text-xs">
          <Popover.Root>
            <Popover.Trigger className="inline-flex items-center gap-1 rounded-md border border-border-light px-2 py-1 hover:bg-surface-secondary">
              <ListFilter size={14} aria-hidden="true" />
              筛选
            </Popover.Trigger>
            <Popover.Portal>
              <Popover.Content align="start" sideOffset={4} aria-label="按列筛选" className="z-50 max-h-[var(--radix-popover-content-available-height)] overflow-y-auto rounded-lg border border-border-light bg-surface-primary p-3 text-xs shadow-lg">
                {choices.map(({ label, values }) => (
                  <fieldset key={label} className="mb-2 min-w-36 last:mb-0">
                    <legend className="font-medium text-text-primary">{label}</legend>
                    {values.map((value) => (
                      <label key={value} className="flex cursor-pointer items-center gap-2 py-1 text-text-secondary">
                        <input type="checkbox" checked={selected[label]?.includes(value) ?? false} onChange={() => toggle(label, value)} />
                        {value}
                      </label>
                    ))}
                  </fieldset>
                ))}
              </Popover.Content>
            </Popover.Portal>
          </Popover.Root>
          {filters.flatMap(({ label }) => (selected[label] ?? []).map((value) => (
            <button key={`${label}：${value}`} type="button" className="rounded-full bg-surface-secondary px-2 py-1 text-text-primary hover:bg-surface-tertiary" onClick={() => toggle(label, value)}>
              {label}：{value} ×
            </button>
          )))}
          {active ? clear : null}
        </div>
      )}
    />
  );
}
