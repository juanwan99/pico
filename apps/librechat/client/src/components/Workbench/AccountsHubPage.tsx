/**
 * Thin door to Wei-Shaw/sub2api account admin. No Pico-built CRUD.
 */
import { PicoIcon } from '~/components/ui/pico-icons';
import { SUB2API_ADMIN_EXIT_URL, SUB2API_ADMIN_URL } from '~/utils/sub2apiAdmin';
import WorkbenchShell from './WorkbenchShell';

export default function AccountsHubPage() {
  return (
    <WorkbenchShell title="账号管理" subtitle="上游订阅账号" backTo="/c/new">
      <div className="mx-auto flex w-full max-w-lg flex-col gap-4 p-6">
        <div className="pico-card flex flex-col gap-3 p-5">
          <span className="flex size-10 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
            <PicoIcon name="user" />
          </span>
          <p className="text-[14px] font-medium">用 Sub2API 管理账号</p>
          <p className="text-[12.5px] leading-5 text-[color:var(--pico-ink-2)]">
            登录、订阅、车队账号都在 Sub2API 真核里。Pico 只开门，不另建账号库，也不把推理打到
            Sub2API。打开后这一页变成 Sub2API 登录页。
          </p>
          <a
            href={SUB2API_ADMIN_URL}
            data-testid="open-sub2api-admin"
            className="mt-1 inline-flex h-10 items-center justify-center rounded-full bg-[color:var(--pico-ink)] px-4 text-[13px] font-medium text-white hover:bg-[color:var(--pico-ink-2)]"
          >
            打开账号管理
          </a>
          <a
            href={SUB2API_ADMIN_EXIT_URL}
            data-testid="exit-sub2api-admin"
            className="text-center text-[12.5px] text-[color:var(--pico-ink-2)] hover:text-[color:var(--pico-ink)]"
          >
            返回 Pico
          </a>
        </div>
      </div>
    </WorkbenchShell>
  );
}
