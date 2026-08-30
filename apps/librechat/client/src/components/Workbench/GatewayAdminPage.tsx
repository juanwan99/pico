/**
 * Owner-only panel: New API pipe + Sub2API login-state + Pico usage.
 * Thin-read monitors (7d / 168h). Soft restore only. Hard re-login on tailnet.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import { SystemRoles } from 'librechat-data-provider';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useAuthContext } from '~/hooks/AuthContext';
import { picoAuthedGet, picoAuthedPost } from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';

const FILTERS = ['全部', '健康', '警告', '严重', '未知'] as const;
type FilterBucket = (typeof FILTERS)[number];

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

function formatAvail(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) {
    return '—';
  }
  const pct = value <= 1 ? value * 100 : value;
  return `${pct.toFixed(1)}%`;
}

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

function TimelineBars({ points }: { points: TimelinePoint[] }) {
  if (points.length === 0) {
    return <p className="mt-2 text-[12px] text-[color:var(--pico-ink-3)]">还没有小时点。</p>;
  }
  return (
    <div
      className="mt-2 flex h-8 w-full items-stretch gap-px overflow-hidden rounded-sm"
      role="img"
      aria-label={`近 ${points.length} 小时`}
    >
      {points.map((point, index) => (
        <span
          key={`${point.checked_at ?? index}-${index}`}
          className={`min-w-[1px] flex-1 ${barColor(point.bucket)}`}
          title={`${point.bucket || '未知'}${point.checked_at ? ` · ${point.checked_at}` : ''}`}
        />
      ))}
    </div>
  );
}

export default function GatewayAdminPage() {
  const { user } = useAuthContext();
  const isAdmin = user?.role === SystemRoles.ADMIN;
  const [status, setStatus] = useState<GatewayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterBucket>('全部');
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
  const filtered = useMemo(
    () => (filter === '全部' ? monitors : monitors.filter((row) => (row.bucket || '未知') === filter)),
    [filter, monitors],
  );
  const counts = useMemo(() => {
    const next: Record<FilterBucket, number> = {
      全部: monitors.length,
      健康: 0,
      警告: 0,
      严重: 0,
      未知: 0,
    };
    for (const row of monitors) {
      const bucket = (row.bucket || '未知') as FilterBucket;
      if (bucket in next && bucket !== '全部') {
        next[bucket] += 1;
      }
    }
    return next;
  }, [monitors]);

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
              ? '要先在尾网 Sub2API 真页签合规承诺。Pico 不代签。'
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
  const sub2extra = compliance
    ? '管理 API 要先在尾网真页签合规承诺。Pico 不代签。'
    : needsAuth
      ? monitorCount == null
        ? '监控卡还是空的。硬重登、签合规、导入订阅号都在尾网 Sub2API 真页。'
        : `监控 ${monitorCount} 条。硬重登仍走尾网真页。`
      : '硬重登走尾网 Sub2API 真页，不接管 pico.aivia.asia。';
  const kinds = status?.usage?.kinds ?? [];
  const emptyMonitors = monitors.length === 0;
  const emptyCopy = compliance
    ? '账号监控要先在尾网 Sub2API 真页签合规。Pico 不代签。'
    : '还没有监控卡。硬重登、签合规、导入订阅号都在尾网 Sub2API 真页。';

  return (
    <WorkbenchShell title="网关管理" subtitle="所有者 · 三本账" backTo="/c/new">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-3 p-6">
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
            {status?.sub2api?.tailnet_ui ? (
              <a
                className="rounded-lg border border-[color:var(--pico-line)] px-4 py-3 text-[13px] text-[color:var(--pico-ink)]"
                href={status.sub2api.tailnet_ui}
                rel="noreferrer"
                target="_blank"
              >
                打开尾网账号台（硬重登 / 合规 / 监控）
              </a>
            ) : null}

            <section className="rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4">
              <p className="text-[14px] font-medium">服务状态 · 近 7 天</p>
              <p className="mt-1 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
                数据来自 Sub2API 渠道监控。Pico 不自建时序库。
              </p>
              <div className="mt-3 flex flex-wrap gap-1.5" role="tablist" aria-label="监控筛选">
                {FILTERS.map((name) => {
                  const active = filter === name;
                  return (
                    <button
                      key={name}
                      type="button"
                      role="tab"
                      aria-selected={active}
                      className={
                        active
                          ? 'rounded-full bg-[color:var(--pico-ink)] px-2.5 py-1 text-[11px] text-[color:var(--pico-surface)]'
                          : 'rounded-full border border-[color:var(--pico-line)] px-2.5 py-1 text-[11px] text-[color:var(--pico-ink-2)]'
                      }
                      onClick={() => setFilter(name)}
                    >
                      {name} {counts[name]}
                    </button>
                  );
                })}
              </div>
              {emptyMonitors ? (
                <p className="mt-3 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">{emptyCopy}</p>
              ) : filtered.length === 0 ? (
                <p className="mt-3 text-[12.5px] text-[color:var(--pico-ink-2)]">这一档没有卡。</p>
              ) : (
                <ul className="mt-3 flex flex-col gap-3">
                  {filtered.map((row) => (
                    <li
                      key={row.id ?? row.name}
                      className="rounded-lg border border-[color:var(--pico-line)] p-3"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <div>
                          <p className="text-[13.5px] font-medium">{row.name || '未命名'}</p>
                          <p className="mt-0.5 text-[12px] text-[color:var(--pico-ink-2)]">
                            {[row.provider, row.primary_model, row.group_name].filter(Boolean).join(' · ')}
                          </p>
                        </div>
                        <div className="text-right">
                          <p className="text-[13px] font-medium tabular-nums">{formatAvail(row.availability_7d)}</p>
                          <p className={`text-[11px] ${bucketText(row.bucket)}`}>{row.bucket || '未知'}</p>
                        </div>
                      </div>
                      <TimelineBars points={row.timeline ?? []} />
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4">
              <p className="text-[14px] font-medium">订阅号登录态</p>
              <p className="mt-1 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
                软按钮只转发刷新 / 测活 / 清错 / 恢复。硬重登仍走尾网真页。
              </p>
              {actionMsg ? (
                <p role="status" className="mt-2 text-[12.5px] text-[color:var(--pico-ink)]">
                  {actionMsg}
                </p>
              ) : null}
              {accounts.length === 0 ? (
                <p className="mt-2 text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
                  {compliance
                    ? '账号列表要先在尾网真页签合规。Pico 不代签。'
                    : '还没有订阅号。导入走尾网 Sub2API 真页。'}
                </p>
              ) : (
                <ul className="mt-3 flex flex-col gap-2">
                  {accounts.map((row) => {
                    const actions = (row.soft_actions ?? Object.keys(SOFT_LABELS)).filter(
                      (name) => name in SOFT_LABELS,
                    );
                    return (
                      <li
                        key={row.id ?? row.name}
                        className="rounded-lg border border-[color:var(--pico-line)] p-3"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <p className="text-[13.5px] font-medium">{row.name || '未命名'}</p>
                            <p className="mt-0.5 text-[12px] text-[color:var(--pico-ink-2)]">
                              {[row.platform, row.status].filter(Boolean).join(' · ')}
                              {row.schedulable === false ? ' · 未调度' : ''}
                            </p>
                            {row.error ? (
                              <p className="mt-1 text-[12px] text-amber-900">{row.error}</p>
                            ) : null}
                          </div>
                        </div>
                        {row.id != null ? (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {actions.map((action) => {
                              const key = `${row.id}:${action}`;
                              return (
                                <button
                                  key={action}
                                  type="button"
                                  className="rounded-md border border-[color:var(--pico-line)] px-2 py-1 text-[11.5px] disabled:opacity-50"
                                  disabled={busy === key}
                                  onClick={() => runSoftAction(row.id as number, action)}
                                >
                                  {SOFT_LABELS[action]}
                                </button>
                              );
                            })}
                          </div>
                        ) : null}
                      </li>
                    );
                  })}
                </ul>
              )}
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
