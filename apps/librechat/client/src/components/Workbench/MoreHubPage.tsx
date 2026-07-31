/**
 * 「更多 · 资料库·灵感」— each tile opens a real secondary surface when ready.
 */
import { useNavigate } from 'react-router-dom';
import {
  FolderOpen,
  Mail,
  FileText,
  Library,
  Lightbulb,
  BookOpen,
  ChevronRight,
} from 'lucide-react';
import WorkbenchShell from './WorkbenchShell';

const ITEMS = [
  {
    id: 'files',
    label: '我的文件',
    desc: '任务账本产物汇总（与右栏结果区同源）',
    icon: FolderOpen,
    href: '/more/files',
    ready: true,
  },
  {
    id: 'inspiration',
    label: '灵感',
    desc: '可复用任务起点 → 技能与专家',
    icon: Lightbulb,
    href: '/capability?tab=skills',
    ready: true,
  },
  {
    id: 'mail',
    label: '我的邮箱',
    desc: '查看接入要求与授权边界',
    icon: Mail,
    href: '/capability/connectors/c3',
    ready: false,
  },
  {
    id: 'docs',
    label: '腾讯文档',
    desc: '文档授权与连接配置',
    icon: FileText,
    href: '/capability/connectors/c5',
    ready: false,
  },
  {
    id: 'ima',
    label: 'ima知识库',
    desc: '知识库索引与检索范围',
    icon: Library,
    href: '/capability/connectors/c4?provider=ima',
    ready: false,
  },
  {
    id: 'lexiang',
    label: '乐享知识库',
    desc: '知识库索引与检索范围',
    icon: BookOpen,
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
          const Icon = item.icon;
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
                  ? 'hover:border-black/12 flex h-full flex-col rounded-lg border border-black/[0.06] bg-white p-4 text-left shadow-sm transition'
                  : 'hover:border-black/12 flex h-full flex-col rounded-lg border border-black/[0.06] bg-white p-4 text-left opacity-80 transition hover:opacity-100'
              }
            >
              <div className="mb-3 flex items-start justify-between">
                <div className="flex size-10 items-center justify-center rounded-xl bg-[#f2f2f2]">
                  <Icon className="h-5 w-5 text-[#3d3d3d]" />
                </div>
                {item.ready ? (
                  <ChevronRight className="h-4 w-4 text-[#b0b0b0]" />
                ) : (
                  <span className="rounded-full bg-[#edf1f4] px-2 py-0.5 text-[11px] text-[#6b6b6b]">
                    待接入
                  </span>
                )}
              </div>
              <p className="text-[14px] font-medium text-[#1a1a1a]">{item.label}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-[#8c8c8c]">{item.desc}</p>
            </button>
          );
        })}
        {unavailableCount > 0 ? (
          <div className="flex flex-col items-start justify-between gap-3 rounded-lg border border-dashed border-black/[0.1] bg-white p-4 dark:border-white/10 dark:bg-surface-primary sm:col-span-2 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-[#3d3d3d] dark:text-text-primary">
                {unavailableCount} 个入口仍待接入
              </p>
              <p className="mt-1 text-[11.5px] text-[#8c8c8c]">
                先从已开放的技能与连接器开始，不会进入空白页面。
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/capability')}
              className="shrink-0 rounded-md bg-[#1a1a1a] px-3 py-1.5 text-[12px] font-medium text-white hover:bg-black"
            >
              查看可用能力
            </button>
          </div>
        ) : null}
      </div>
    </WorkbenchShell>
  );
}
