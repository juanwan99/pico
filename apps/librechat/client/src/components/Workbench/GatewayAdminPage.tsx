/**
 * Manager-only panel: New API reverse proxy + Sub2API account pool.
 * Not a teacher page. Sub2API is not the product frontend.
 */
import { useEffect, useState } from 'react';
import { SystemRoles } from 'librechat-data-provider';
import { PicoIcon } from '~/components/ui/pico-icons';
import { useAuthContext } from '~/hooks/AuthContext';
import { picoAuthedGet } from '~/data-provider/pico/api';
import WorkbenchShell from './WorkbenchShell';

type Probe = { bind?: string; role?: string; ok?: boolean; http?: number };
type GatewayStatus = {
  ok?: boolean;
  audience?: string;
  pico_talks_to?: string;
  sub2api_role?: string;
  sub2api_is_frontend?: boolean;
  dify?: string;
  new_api?: Probe;
  sub2api?: Probe;
};

function ProbeRow({ title, probe }: { title: string; probe?: Probe }) {
  const ok = probe?.ok === true;
  return (
    <div className="flex items-start justify-between gap-3 rounded-lg border border-[color:var(--pico-line)] bg-[color:var(--pico-surface)] p-4">
      <div>
        <p className="text-[14px] font-medium">{title}</p>
        <p className="mt-1 text-[12.5px] text-[color:var(--pico-ink-2)]">
          {probe?.role ?? ''} · {probe?.bind ?? ''}
        </p>
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
      <WorkbenchShell title="网关管理" subtitle="管理者" backTo="/c/new">
        <p className="p-6 text-[13px] text-[color:var(--pico-ink-2)]">这页只给管理者，老师账号看不见内容。</p>
      </WorkbenchShell>
    );
  }

  return (
    <WorkbenchShell title="网关管理" subtitle="账号轮询反代" backTo="/c/new">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-3 p-6">
        <div className="pico-card flex flex-col gap-2 p-5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
            <PicoIcon name="shield" />
          </span>
          <p className="text-[14px] font-medium">New API 反代 · Sub2API 账号池</p>
          <p className="text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
            Pico 只打 New API。Sub2API 在 loopback 给 New API 做上游账号轮询，不当老师前端，也不接管
            pico.aivia.asia。Dify 已退役。
          </p>
        </div>
        {error ? (
          <p role="alert" className="text-[13px] text-amber-900">
            {error}
          </p>
        ) : (
          <>
            <ProbeRow title="New API 反代" probe={status?.new_api} />
            <ProbeRow title="Sub2API 账号池" probe={status?.sub2api} />
          </>
        )}
      </div>
    </WorkbenchShell>
  );
}
