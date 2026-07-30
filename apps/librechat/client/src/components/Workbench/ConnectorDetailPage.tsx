/**
 * 连接器详情 — 点击连接器后进入（业务占位 + 明确后置边界）.
 */
import { useMemo } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Plug, Shield } from 'lucide-react';
import WorkbenchShell from './WorkbenchShell';

const CATALOG: Record<
  string,
  { name: string; desc: string; status: 'ready' | 'add'; scope: string; note: string }
> = {
  c1: {
    name: 'MCP 通用',
    desc: '已配置的 MCP 服务器（白名单工具）',
    status: 'ready',
    scope: '只读查询 · 需在设置中启用',
    note: '浏览器版不开放任意远程代码执行；危险工具默认关。',
  },
  c2: {
    name: '自定义连接器',
    desc: 'OpenAPI / Webhook',
    status: 'add',
    scope: '后置',
    note: '需单独安全评审后接入，不在当前演示范围。',
  },
  c3: {
    name: '邮箱',
    desc: '智能体邮箱',
    status: 'add',
    scope: '后置',
    note: 'WorkBuddy 桌面/授权能力，浏览器版后置。',
  },
  c4: {
    name: '知识库',
    desc: '文档索引连接',
    status: 'add',
    scope: '后置',
    note: '可后续接向量检索；当前用任务附件与结果区代替。',
  },
};

export default function ConnectorDetailPage() {
  const { connectorId } = useParams();
  const navigate = useNavigate();
  const item = useMemo(
    () => CATALOG[connectorId || ''] || {
      name: '未知连接器',
      desc: '',
      status: 'add' as const,
      scope: '—',
      note: '未在目录中。',
    },
    [connectorId],
  );

  return (
    <WorkbenchShell title={item.name} subtitle="连接器" backTo="/capability?tab=connectors">
      <div className="mx-auto max-w-xl space-y-4 p-6">
        <div className="rounded-2xl border border-black/[0.06] bg-white p-5">
          <div className="flex items-start gap-3">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-[#edf1f4]">
              <Plug className="h-6 w-6" />
            </div>
            <div>
              <p className="text-[16px] font-semibold">{item.name}</p>
              <p className="mt-1 text-[13px] text-[#6b6b6b]">{item.desc}</p>
              <span
                className={
                  item.status === 'ready'
                    ? 'mt-2 inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-800'
                    : 'mt-2 inline-flex rounded-full bg-[#edf1f4] px-2 py-0.5 text-[11px] text-[#6b6b6b]'
                }
              >
                {item.status === 'ready' ? '可用（受限）' : '后置 · 不可配置'}
              </span>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-black/[0.06] bg-white p-5">
          <div className="mb-2 flex items-center gap-2 text-[13px] font-medium">
            <Shield className="h-4 w-4" />
            权限与范围
          </div>
          <p className="text-[13px] text-[#3d3d3d]">{item.scope}</p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-[#8c8c8c]">{item.note}</p>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            disabled={item.status !== 'ready'}
            onClick={() => navigate('/c/new')}
            className="rounded-xl bg-[#1a1a1a] px-4 py-2.5 text-[13px] font-medium text-white disabled:opacity-40"
          >
            在任务中使用
          </button>
          <button
            type="button"
            onClick={() => navigate('/capability')}
            className="rounded-xl border border-black/[0.08] px-4 py-2.5 text-[13px]"
          >
            返回能力中心
          </button>
        </div>
      </div>
    </WorkbenchShell>
  );
}
