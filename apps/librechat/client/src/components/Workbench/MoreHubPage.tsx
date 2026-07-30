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
    desc: '智能体邮箱 · 需开通',
    icon: Mail,
    href: null as string | null,
    ready: false,
  },
  {
    id: 'docs',
    label: '腾讯文档',
    desc: '授权墙能力',
    icon: FileText,
    href: null,
    ready: false,
  },
  {
    id: 'ima',
    label: 'ima知识库',
    desc: '知识库连接',
    icon: Library,
    href: null,
    ready: false,
  },
  {
    id: 'lexiang',
    label: '乐享知识库',
    desc: '知识库连接',
    icon: BookOpen,
    href: null,
    ready: false,
  },
] as const;

export default function MoreHubPage() {
  const navigate = useNavigate();

  return (
    <WorkbenchShell title="更多 · 资料库·灵感" subtitle="扩展入口">
      <div className="mx-auto grid w-full max-w-3xl grid-cols-1 gap-3 p-6 sm:grid-cols-2">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              disabled={!item.ready}
              onClick={() => {
                if (item.href) {
                  navigate(item.href);
                }
              }}
              className={
                item.ready
                  ? 'flex h-full flex-col rounded-2xl border border-black/[0.06] bg-white p-4 text-left shadow-sm transition hover:border-black/12'
                  : 'flex h-full flex-col rounded-2xl border border-black/[0.06] bg-white p-4 text-left opacity-75'
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
                    后置
                  </span>
                )}
              </div>
              <p className="text-[14px] font-medium text-[#1a1a1a]">{item.label}</p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-[#8c8c8c]">{item.desc}</p>
            </button>
          );
        })}
      </div>
    </WorkbenchShell>
  );
}
