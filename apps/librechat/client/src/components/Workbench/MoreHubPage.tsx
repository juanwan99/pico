/**
 * 「更多 · 资料库·灵感」入口页（clean-room IA）。
 * 腾讯系授权能力仅占位后置。
 */
import { Link } from 'react-router-dom';
import {
  FolderOpen,
  Mail,
  FileText,
  Library,
  Lightbulb,
  BookOpen,
} from 'lucide-react';

const ITEMS = [
  {
    id: 'files',
    label: '我的文件',
    desc: '任务成果与云端网盘（浏览器托管目录）',
    icon: FolderOpen,
    href: '/c/new',
    ready: false,
  },
  {
    id: 'mail',
    label: '我的邮箱',
    desc: '智能体邮箱 · 需开通（后置）',
    icon: Mail,
    href: '#',
    ready: false,
  },
  {
    id: 'docs',
    label: '腾讯文档',
    desc: '授权墙能力 · 后置',
    icon: FileText,
    href: '#',
    ready: false,
  },
  {
    id: 'ima',
    label: 'ima知识库',
    desc: '知识库连接 · 后置',
    icon: Library,
    href: '#',
    ready: false,
  },
  {
    id: 'lexiang',
    label: '乐享知识库',
    desc: '知识库连接 · 后置',
    icon: BookOpen,
    href: '#',
    ready: false,
  },
  {
    id: 'inspiration',
    label: '灵感',
    desc: '可复用任务起点（P1 接技能/提示模板）',
    icon: Lightbulb,
    href: '/skills',
    ready: true,
  },
] as const;

export default function MoreHubPage() {
  return (
    <div className="flex h-full flex-col bg-[#fafafa] dark:bg-presentation">
      <header className="flex h-12 items-center border-b border-black/[0.06] bg-white px-4 dark:border-border-light dark:bg-surface-primary">
        <h1 className="text-[15px] font-semibold text-[#1a1a1a] dark:text-text-primary">
          更多 · 资料库·灵感
        </h1>
      </header>
      <div className="mx-auto grid w-full max-w-3xl grid-cols-1 gap-3 p-6 sm:grid-cols-2">
        {ITEMS.map((item) => {
          const Icon = item.icon;
          const body = (
            <div className="flex h-full flex-col rounded-2xl border border-black/[0.06] bg-white p-4 shadow-sm transition hover:border-black/10 dark:border-border-light dark:bg-surface-secondary">
              <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-[#f2f2f2] dark:bg-surface-tertiary">
                <Icon className="h-5 w-5 text-[#3d3d3d] dark:text-text-primary" />
              </div>
              <p className="text-[14px] font-medium text-[#1a1a1a] dark:text-text-primary">
                {item.label}
              </p>
              <p className="mt-1 text-[12.5px] leading-relaxed text-[#8c8c8c]">{item.desc}</p>
              {!item.ready && (
                <span className="mt-3 inline-flex w-fit rounded-full bg-[#edf1f4] px-2 py-0.5 text-[11px] text-[#6b6b6b]">
                  后置
                </span>
              )}
            </div>
          );
          if (item.href === '#') {
            return (
              <div key={item.id} className="opacity-90">
                {body}
              </div>
            );
          }
          return (
            <Link key={item.id} to={item.href}>
              {body}
            </Link>
          );
        })}
      </div>
    </div>
  );
}
