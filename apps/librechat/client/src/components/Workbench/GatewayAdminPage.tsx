/**
 * Owner-only panel: New API pipe + Sub2API login-state + Pico usage.
 * Thin-read monitors (7d / 168h). Soft restore only. Hard re-login on public Sub2API.
 */
import { useCallback, useEffect, useState } from 'react';
import type { TableColumn } from '@librechat/client';
import { SystemRoles } from 'librechat-data-provider';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useAuthContext } from '~/hooks/AuthContext';
import { picoAuthedGet, picoAuthedPost } from '~/data-provider/pico/api';
import PicoListTable from './PicoListTable';
import WorkbenchShell from './WorkbenchShell';

const SOFT_LABELS: Record<string, string> = {
  refresh: '刷新',
  test: '测活',
  'clear-error': '清错',
  'recover-state': '恢复',
};

type Probe = {
  bind?: string;
  intended_bind?: string;
  role?: string;
  ok?: boolean;
  http?: number;
  models?: string[];
  account_ui?: string;
  tailnet_ui?: string;
  monitors_http?: number;
  accounts_http?: number;
  monitor_count?: number | null;
  compliance_required?: boolean;
  needs_auth?: boolean;
  monitors?: MonitorCard[];
  accounts?: AccountRow[];
};
type TimelinePoint = { status?: string; bucket?: string; checked_at?: string };
type MonitorCard = {
  id?: number | null;
  name?: string;
  provider?: string;
  group_name?: string;
  primary_model?: string;
  primary_status?: string;
  bucket?: string;
  primary_latency_ms?: number | null;
  availability_7d?: number | null;
  timeline?: TimelinePoint[];
};
type AccountRow = {
  id?: number | null;
  name?: string;
  platform?: string;
  status?: string;
  schedulable?: boolean | null;
  error?: string | null;
  soft_actions?: string[];
};
type UsageKind = {
  kind?: string;
  event_count?: number;
  total_tokens?: number | null;
  unknown_count?: number;
};
type GatewayStatus = {
  ok?: boolean;
  audience?: string;
  pico_talks_to?: string;
  sub2api_role?: string;
  sub2api_is_frontend?: boolean;
  new_api_role?: string;
  dify?: string;
  brain?: { model?: string | null; via?: string; expected_via?: string };
  new_api?: Probe;
  sub2api?: Probe;
  usage?: { ok?: boolean; billing?: boolean; day?: string; kinds?: UsageKind[]; note?: string };
};

function barColor(bucket?: string): string {
  if (bucket === '健康') {
    return 'bg-emerald-500';
  }
  if (bucket === '警告') {
    return 'bg-amber-400';
  }
  if (bucket === '严重') {
    return 'bg-rose-500';
  }
  return 'bg-zinc-300';
}

function bucketText(bucket?: string): string {
  if (bucket === '健康') {
    return 'text-emerald-700';
  }
  if (bucket === '警告') {
    return 'text-amber-800';
  }
  if (bucket === '严重') {
    return 'text-rose-700';
  }
  return 'text-zinc-500';
}

function availability(row: MonitorCard): number | undefined {
  const value = row.availability_7d;
  return value == null || Number.isNaN(value) ? undefined : value <= 1 ? value * 100 : value;
}

const monitorFilters = [
  { label: '健康档', value: (row: MonitorCard) => row.bucket || '未知' },
  { label: '提供方', value: (row: MonitorCard) => row.provider || '—' },
];
const accountFilters = [
  { label: '平台', value: (row: AccountRow) => row.platform || '—' },
  { label: '登录态', value: (row: AccountRow) => row.status || '—' },
  { label: '调度', value: (row: AccountRow) =>
    row.schedulable == null ? '未知' : row.schedulable ? '可调度' : '未调度' },
];

function ProbeRow({ title, probe, extra }: { title: string; probe?: Probe; extra?: string }) {
  const ok = probe?.ok === true;
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4">
      <div>
        <p className="text-[14px] font-medium">{title}</p>
        <p className="mt-1 text-[12.5px] text-[color:var(--pico-ink-2)]">
          {probe?.role ?? ''} · {probe?.bind ?? probe?.intended_bind ?? ''}
        </p>
        {extra ? <p className="mt-1 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">{extra}</p> : null}
      </div>
      <span
        className={
          ok
            ? 'rounded-full bg-emerald-50 px-1.5 py-0.5 text-[10px] text-emerald-800'
            : 'rounded-full bg-amber-50 px-1.5 py-0.5 text-[10px] text-amber-900'
        }
      >
        {ok ? '在岗' : '未通'}
      </span>
    </div>
  );
}

function listEmpty(http: number | undefined, empty: string, compliance: string) {
  if (http == null || http === 200) return empty;
  if (http === 423) return <span role="alert">{compliance}</span>;
  if (http === 401) return <span role="alert">账号台鉴权失败，请重新登录。</span>;
  return <span role="alert">读取失败（{http || '上游未响应'}）。</span>;
}

function TimelineBars({ points }: { points: TimelinePoint[] }) {
  if (points.length === 0) {
    return <p className="text-xs text-text-secondary">还没有小时点。</p>;
  }
  return (
    <div
      className="flex h-4 w-full items-stretch gap-[0.35px] overflow-hidden rounded-sm"
      role="img"
      aria-label={`近 ${points.length} 小时`}
    >
      {points.map((point, index) => (
        <span
          key={`${point.checked_at ?? index}-${index}`}
          className={`min-w-0 flex-1 ${barColor(point.bucket)}`}
          title={`${point.bucket || '未知'}${point.checked_at ? ` · ${point.checked_at}` : ''}`}
        />
      ))}
    </div>
  );
}

const monitorColumns: TableColumn<MonitorCard, unknown>[] = [
  {
    id: 'name', header: '渠道', sortingFn: 'alphanumeric', accessorFn: (row) => row.name || '未命名',
    meta: { isRowHeader: true, width: 26 },
    cell: ({ row: { original: row }, getValue }) => (
      <>
        <span title={row.name}>{String(getValue())}</span>
        <p className="truncate text-xs text-text-secondary" title={[row.primary_model, row.group_name].filter(Boolean).join(' · ')}>
          {[row.primary_model, row.group_name].filter(Boolean).join(' · ')}
        </p>
      </>
    ),
  },
  { id: 'provider', header: '提供方', sortingFn: 'alphanumeric', accessorFn: monitorFilters[1].value, meta: { width: 13 } },
  { id: 'bucket', header: '健康档', accessorFn: monitorFilters[0].value, enableSorting: false,
    meta: { width: 10 }, cell: ({ getValue }) => <span className={bucketText(String(getValue()))}>{String(getValue())}</span> },
  {
    id: 'availability', header: '7 日可用率', accessorFn: availability,
    meta: { width: 14, className: 'whitespace-nowrap' },
    cell: ({ getValue }) => {
      const pct = getValue<number | undefined>();
      return pct == null ? '—' : `${pct.toFixed(1)}%`;
    },
  },
  { id: 'latency', header: '延迟', meta: { width: 9 },
    cell: ({ row: { original: row } }) => row.primary_latency_ms == null ? '—' : `${row.primary_latency_ms} ms` },
  { id: 'timeline', header: '近 7 天小时状态', meta: { width: 28 },
    cell: ({ row: { original: row } }) => <TimelineBars points={row.timeline ?? []} /> },
];

export default function GatewayAdminPage() {
  const { user } = useAuthContext();
  const isAdmin = user?.role === SystemRoles.ADMIN;
  const [status, setStatus] = useState<GatewayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const loadStatus = useCallback(() => {
    return picoAuthedGet('/api/pico/v1/admin/gateway').then(async (res) => {
      if (!res.ok) {
        throw new Error(res.status === 403 ? '不是管理者账号' : '网关状态读不到');
      }
      return res.json() as Promise<GatewayStatus>;
    });
  }, []);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    let cancelled = false;
    loadStatus()
      .then((body) => {
        if (!cancelled) {
          setStatus(body);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : '网关状态读不到');
        }
      });
    return () => {
      cancelled = true;
    };
  }, [isAdmin, loadStatus]);

  const monitors = status?.sub2api?.monitors ?? [];
  const accounts = status?.sub2api?.accounts ?? [];
  async function runSoftAction(accountId: number, action: string) {
    setBusy(`${accountId}:${action}`);
    setActionMsg(null);
    try {
      const res = await picoAuthedPost(`/api/pico/v1/admin/gateway/accounts/${accountId}/${action}`);
      const body = (await res.json().catch(() => ({}))) as { ok?: boolean; message?: string };
      if (!res.ok || body.ok === false) {
        setActionMsg(
          body.message ||
            (res.status === 423
              ? '要先在账号台签合规承诺。Pico 不代签。'
              : '没做成。'),
        );
        return;
      }
      setActionMsg(body.message || '已交给上游。');
      const next = await loadStatus().catch(() => null);
      if (next) {
        setStatus(next);
      }
    } catch {
      setActionMsg('没做成。');
    } finally {
      setBusy(null);
    }
  }

  if (!isAdmin) {
    return (
      <WorkbenchShell title="网关管理" subtitle="所有者" backTo="/c/new">
        <p className="p-6 text-[13px] text-[color:var(--pico-ink-2)]">这页只给所有者，老师账号看不见内容。</p>
      </WorkbenchShell>
    );
  }

  const brainVia = status?.brain?.via ?? '';
  const brainOk = brainVia === 'new_api';
  const models = (status?.new_api?.models ?? []).join('、');
  const monitorCount = status?.sub2api?.monitor_count;
  const compliance = status?.sub2api?.compliance_required === true;
  const needsAuth = status?.sub2api?.needs_auth === true;
  const accountUi = status?.sub2api?.account_ui || status?.sub2api?.tailnet_ui;
  const sub2extra = compliance
    ? '管理 API 要先在账号台签合规承诺。Pico 不代签。'
    : needsAuth
      ? monitorCount == null
        ? '硬重登、签合规、导入订阅号都在账号台。'
        : `监控 ${monitorCount} 条。硬重登仍走账号台。`
      : '硬重登走账号台，不接管 pico.aivia.asia。';
  const kinds = status?.usage?.kinds ?? [];
  const accountColumns: TableColumn<AccountRow, unknown>[] = [
    {
      id: 'name', header: '订阅号', sortingFn: 'alphanumeric', accessorFn: (row) => row.name || '未命名',
      meta: { isRowHeader: true, width: 28 },
      cell: ({ row: { original: row }, getValue }) => (
        <>
          <span title={row.name}>{String(getValue())}</span>
          {row.error && <p className="truncate text-xs text-amber-800" title={row.error}>{row.error}</p>}
        </>
      ),
    },
    { id: 'platform', header: '平台', sortingFn: 'alphanumeric', accessorFn: accountFilters[0].value, meta: { width: 13 } },
    { id: 'status', header: '登录态', accessorFn: accountFilters[1].value, enableSorting: false, meta: { width: 13 } },
    { id: 'schedule', header: '调度', accessorFn: accountFilters[2].value, enableSorting: false, meta: { width: 12 } },
    {
      id: 'actions', header: '操作', meta: { width: 34 },
      cell: ({ row: { original: row } }) => {
        const { id } = row;
        const actions = (row.soft_actions ?? Object.keys(SOFT_LABELS)).filter((action) => action in SOFT_LABELS);
        return id != null && (
          <div className="flex flex-wrap gap-1">
            {actions.map((action) => (
              <button key={action} type="button" disabled={busy === `${id}:${action}`}
                onClick={() => void runSoftAction(id, action)}
                className="rounded border border-border-light px-2 py-1 text-xs hover:bg-surface-secondary disabled:opacity-50">
                {SOFT_LABELS[action]}
              </button>
            ))}
          </div>
        );
      },
    },
  ];

  return (
    <WorkbenchShell title="网关管理" subtitle="所有者 · 三本账" backTo="/c/new">
      <div className="mx-auto flex w-full max-w-5xl flex-col gap-3 p-6">
        <div className="pico-card flex flex-col gap-2 p-5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
            <PicoIcon name="shield" />
          </span>
          <p className="text-[14px] font-medium">老师走 Pico · 管道 New API · 账号 Sub2API</p>
          <p className="text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
            Pico 只打 New API。AIProxy / Sub2API 都是管道上游，不当老师前端，也不接管 pico.aivia.asia。Dify
            已退役。
          </p>
        </div>
        {error ? (
          <p role="alert" className="text-[13px] text-amber-900">
            {error}
          </p>
        ) : (
          <>
            <ProbeRow
              title="管道 · New API"
              probe={status?.new_api}
              extra={
                brainOk
                  ? `聊天脑已走 New API${status?.brain?.model ? ` · ${status.brain.model}` : ''}${models ? ` · ${models}` : ''}`
                  : `聊天脑仍直连 ${brainVia || '未知'}，应改走 New API 再谈多模型协作。${models ? ` 渠道模型：${models}` : ''}`
              }
            />
            <ProbeRow title="账号 · Sub2API 登录态" probe={status?.sub2api} extra={sub2extra} />
            {accountUi ? (
              <a
                className="rounded-lg border border-[color:var(--pico-line)] px-4 py-3 text-[13px] text-[color:var(--pico-ink)]"
                href={accountUi}
                rel="noreferrer"
                target="_blank"
              >
                打开账号台（硬重登 / 合规 / 监控）
              </a>
            ) : null}

            <section aria-label="服务状态 · 近 7 天" className="pico-card space-y-2 p-4">
              <h2 className="text-sm font-medium">服务状态 · 近 7 天</h2>
              <PicoListTable data={monitors} columns={monitorColumns} filters={monitorFilters}
                emptyState={listEmpty(status?.sub2api?.monitors_http, '还没有渠道监控记录。', '账号监控要先在账号台签合规。Pico 不代签。')} />
            </section>

            <section aria-label="订阅号登录态" className="pico-card space-y-2 p-4">
              <h2 className="text-sm font-medium">订阅号登录态</h2>
              {actionMsg ? <p role="status" className="text-xs">{actionMsg}</p> : null}
              <PicoListTable data={accounts} columns={accountColumns} filters={accountFilters}
                emptyState={listEmpty(status?.sub2api?.accounts_http, '还没有订阅号。导入走账号台。', '账号列表要先在账号台签合规。Pico 不代签。')} />
            </section>

            <div className="rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4">
              <p className="text-[14px] font-medium">用户消耗 · Pico usage_events</p>
              <p className="mt-1 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
                {status?.usage?.note ?? '老师用量。管道成本在 New API。钱在 edu-core。'}
              </p>
              {kinds.length === 0 ? (
                <p className="mt-2 text-[12.5px] text-[color:var(--pico-ink-2)]">
                  {status?.usage?.day ? `${status.usage.day} 还没有事件。` : '用量还没读到。'}
                </p>
              ) : (
                <ul className="mt-2 flex flex-col gap-1 text-[12.5px] text-[color:var(--pico-ink-2)]">
                  {kinds.map((row) => (
                    <li key={row.kind}>
                      {row.kind} · {row.event_count ?? 0} 次
                      {row.total_tokens != null ? ` · ${row.total_tokens} token` : ''}
                      {row.unknown_count ? ` · ${row.unknown_count} 未知` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </div>
    </WorkbenchShell>
  );
}
