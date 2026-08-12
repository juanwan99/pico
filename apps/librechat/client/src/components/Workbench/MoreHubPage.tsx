/**
 * 「更多 · 资料库·灵感」— each tile opens a real secondary surface when ready.
 */
import { useNavigate } from 'react-router-dom';
import { PicoIcon, type PicoIconName } from '~/components/ui/pico-icons';
import WorkbenchShell from './WorkbenchShell';

const ITEMS = [
  {
    id: 'files',
    label: '我的文件',
    desc: '任务账本产物汇总（与右栏结果区同源）',
    icon: 'folder-open',
    href: '/more/files',
    ready: true,
  },
  {
    id: 'inspiration',
    label: '灵感',
    desc: '可复用任务起点 → 技能与专家',
    icon: 'lightbulb',
    href: '/capability?tab=skills',
    ready: true,
  },
  {
    id: 'mail',
    label: '我的邮箱',
    desc: '查看接入要求与授权边界',
    icon: 'mail',
    href: '/capability/connectors/c3',
    ready: false,
  },
  {
    id: 'docs',
    label: '腾讯文档',
    desc: '文档授权与连接配置',
    icon: 'doc',
    href: '/capability/connectors/c5',
    ready: false,
  },
  {
    id: 'ima',
    label: 'ima知识库',
    desc: '知识库索引与检索范围',
    icon: 'books',
    href: '/capability/connectors/c4?provider=ima',
    ready: false,
  },
  {
    id: 'lexiang',
    label: '乐享知识库',
    desc: '知识库索引与检索范围',
    icon: 'books',
    href: '/capability/connectors/c4?provider=lexiang',
    ready: false,
  },
] as const;

export default function MoreHubPage() {
  const navigate = useNavigate();
  const unavailableCount = ITEMS.filter((item) => !item.ready).length;

  return (
    <WorkbenchShell title="更多 · 资料库·灵感" subtitle="扩展入口">
      <div className="mx-auto grid w-full max-w-3xl grid-cols-1 gap-3 p-6 sm:grid-cols-2">
        {ITEMS.map((item) => {
          const icon = item.icon as PicoIconName;
          return (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                if (item.href) {
                  navigate(item.href);
                }
              }}
              className={
                item.ready
                  ? 'pico-card pico-card-interactive flex h-full flex-col p-5 text-left'
                  : 'pico-card pico-card-interactive flex h-full flex-col p-5 text-left opacity-75 hover:opacity-100'
              }
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="pico-icon-medallion">
                  <PicoIcon name={icon} />
                </div>
                {item.ready ? (
                  <PicoIcon name="arrow" size="sm" className="text-[color:var(--pico-ink-3)]" />
                ) : (
                  <span className="rounded-full bg-[color:var(--pico-surface-2)] px-2.5 py-1 text-[11px] text-[color:var(--pico-ink-2)]">
                    待接入
                  </span>
                )}
              </div>
              <p className="text-[14px] font-semibold text-[color:var(--pico-ink)]">{item.label}</p>
              <p className="mt-1.5 text-[12.5px] leading-relaxed text-[color:var(--pico-ink-2)]">
                {item.desc}
              </p>
            </button>
          );
        })}
        {unavailableCount > 0 ? (
          <div className="flex flex-col items-start justify-between gap-3 rounded-[var(--pico-radius-sm)] border border-dashed border-[color:var(--pico-line-2)] bg-[color:var(--pico-surface)] p-4 dark:border-white/10 dark:bg-surface-primary sm:col-span-2 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-[color:var(--pico-ink)] dark:text-text-primary">
                {unavailableCount} 个入口仍待接入
              </p>
              <p className="mt-1 text-[11.5px] text-[color:var(--pico-ink-2)]">
                先从已开放的技能与连接器开始，不会进入空白页面。
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/capability')}
              className="pico-cta-accent shrink-0 px-4 py-2 text-[12px] font-medium"
            >
              查看可用能力
            </button>
          </div>
        ) : null}
      </div>
    </WorkbenchShell>
  );
}
