/**
 * Owner-only panel: New API pipe + Sub2API login-state + Pico usage.
 * Not a teacher page. Sub2API is not the product frontend.
 */
import { useEffect, useState } from 'react';
import { SystemRoles } from 'librechat-data-provider';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useAuthContext } from '~/hooks/AuthContext';
import { picoAuthedGet } from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';

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

export default function GatewayAdminPage() {
  const { user } = useAuthContext();
  const isAdmin = user?.role === SystemRoles.ADMIN;
  const [status, setStatus] = useState<GatewayStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isAdmin) {
      return;
    }
    let cancelled = false;
    picoAuthedGet('/api/pico/v1/admin/gateway')
      .then(async (res) => {
        if (!res.ok) {
          throw new Error(res.status === 403 ? '不是管理者账号' : '网关状态读不到');
        }
        return res.json() as Promise<GatewayStatus>;
      })
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
  }, [isAdmin]);

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
  const sub2extra = status?.sub2api?.compliance_required
    ? '管理 API 要先在尾网真页签合规承诺。Pico 不代签。'
    : status?.sub2api?.needs_auth
      ? monitorCount == null
        ? '监控卡还是空的。硬重登、签合规、导入订阅号都在尾网 Sub2API 真页。'
        : `监控 ${monitorCount} 条。硬重登仍走尾网真页。`
      : '硬重登走尾网 Sub2API 真页，不接管 pico.aivia.asia。';
  const kinds = status?.usage?.kinds ?? [];

  return (
    <WorkbenchShell title="网关管理" subtitle="所有者 · 三本账" backTo="/c/new">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-3 p-6">
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
