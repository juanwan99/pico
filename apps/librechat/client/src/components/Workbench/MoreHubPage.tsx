/**
 * Legacy /more hub. Left rail no longer links here; keep a thin pointer.
 */
import { useNavigate } from 'react-router-dom';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import { setPicoSidebarRail, type PicoSidebarRail } from '~/utils/picoSidebarRail';
import WorkbenchShell from './WorkbenchShell';

const ITEMS: Array<{
  id: string;
  label: string;
  desc: string;
  icon: PicoIconName;
  href: string;
  rail?: PicoSidebarRail;
}> = [
  {
    id: 'files',
    label: '我的文件',
    desc: '本人做成的文件',
    icon: 'folder',
    href: '/c/new',
    rail: 'files',
  },
  {
    id: 'school',
    label: '学校材料',
    desc: '学校场里的材料',
    icon: 'books',
    href: '/c/new',
    rail: 'school',
  },
  {
    id: 'capability',
    label: '技能与连接器',
    desc: '技能开关 · 学校知识库与 MCP',
    icon: 'blocks',
    href: '/capability',
  },
  {
    id: 'accounts',
    label: '账号管理',
    desc: 'Sub2API 登录 · 上游订阅账号',
    icon: 'user',
    href: '/accounts',
  },
];

export default function MoreHubPage() {
  const navigate = useNavigate();

  return (
    <WorkbenchShell title="更多" subtitle="入口已收到左侧">
      <div className="mx-auto grid w-full max-w-3xl grid-cols-1 gap-3 p-6 sm:grid-cols-2">
        {ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => {
              if (item.rail) setPicoSidebarRail(item.rail);
              navigate(item.href);
            }}
            className="pico-card pico-card-interactive flex h-full flex-col p-5 text-left"
          >
            <span className="mb-3 flex size-10 items-center justify-center rounded-xl bg-[color:var(--pico-surface-2)]">
              <PicoIcon name={item.icon} />
            </span>
            <p className="text-[14px] font-medium">{item.label}</p>
            <p className="mt-1 text-[12.5px] text-[color:var(--pico-ink-2)]">{item.desc}</p>
          </button>
        ))}
      </div>
    </WorkbenchShell>
  );
}
