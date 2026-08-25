/**
 * 连接器详情 — 配置草稿、权限边界与任务/项目绑定。
 */
import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { PicoIcon } from '~/components/ui/pico-icons';
import WorkbenchShell from './WorkbenchShell';

const CATALOG: Record<
  string,
  { name: string; desc: string; status: 'ready' | 'add'; scope: string; note: string }
> = {
  mcp: {
    name: 'MCP',
    desc: '通用 MCP 工具桥',
    status: 'add',
    scope: '未接通',
    note: '当前没有接好的 MCP 服务器。不开放任意远程代码执行。',
  },
  'school-kb': {
    name: '学校知识库',
    desc: '学校场里已挂上的材料',
    status: 'ready',
    scope: '只读检索已挂载材料',
    note: '已接通。对话里点名一场即可引用；不是邮箱或腾讯文档空壳。',
  },
};

export default function ConnectorDetailPage() {
  const { connectorId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const projectId = params.get('projectId');
  const returnTo = params.get('return');
  const item = useMemo(
    () =>
      CATALOG[connectorId || ''] || {
        name: '不在目录里',
        desc: '',
        status: 'add' as const,
        scope: '—',
        note: '连接器只列学校知识库和 MCP。邮箱、腾讯文档等空壳已收掉。',
      },
    [connectorId],
  );
  const storageKey = `pico:connectorDraft:${connectorId || 'unknown'}`;
  const [label, setLabel] = useState('');
  const [endpoint, setEndpoint] = useState('');
  const [scope, setScope] = useState(item.scope);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setScope(item.scope);
    try {
      const raw = localStorage.getItem(storageKey);
      if (!raw) {
        return;
      }
      const draft = JSON.parse(raw) as { label?: string; endpoint?: string; scope?: string };
      setLabel(draft.label || '');
      setEndpoint(draft.endpoint || '');
      setScope(draft.scope || item.scope);
    } catch {
      /* ignore invalid local draft */
    }
  }, [item.scope, storageKey]);

  const saveDraft = () => {
    try {
      localStorage.setItem(storageKey, JSON.stringify({ label, endpoint, scope }));
      setSaved(true);
      window.setTimeout(() => setSaved(false), 1600);
    } catch {
      setSaved(false);
    }
  };

  const useConnector = () => {
    if (connectorId === 'school-kb') {
      navigate('/more/files#school');
      return;
    }
    if (projectId && returnTo) {
      navigate(returnTo);
    }
  };

  return (
    <WorkbenchShell title={item.name} subtitle="连接器" backTo="/capability?tab=connectors">
      <div className="mx-auto w-full max-w-2xl space-y-3 p-5">
        <div className="pico-card p-5">
          <div className="flex items-start gap-3">
            <div className="pico-icon-medallion size-11">
              <PicoIcon name="plug" size="lg" />
            </div>
            <div>
              <p className="text-[16px] font-semibold">{item.name}</p>
              <p className="mt-1 text-[13px] text-[color:var(--pico-ink-2)]">{item.desc}</p>
              <span
                className={
                  item.status === 'ready'
                    ? 'mt-2 inline-flex rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-800'
                    : 'mt-2 inline-flex rounded-full bg-[color:var(--pico-surface-2)] px-2 py-0.5 text-[11px] text-[color:var(--pico-ink-2)]'
                }
              >
                {item.status === 'ready' ? '已接通' : '未接'}
              </span>
            </div>
          </div>
        </div>

        <div className="pico-panel p-4">
          <div className="mb-2 flex items-center gap-2 text-[13px] font-medium">
            <PicoIcon name="shield" size="sm" />
            权限与范围
          </div>
          <p className="text-[13px] text-[color:var(--pico-ink)]">{scope}</p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-[color:var(--pico-ink-2)]">
            {item.note}
          </p>
        </div>

        <div className="pico-panel p-4">
          <div className="mb-3">
            <p className="text-[13px] font-medium">连接配置</p>
            <p className="mt-0.5 text-[11.5px] text-[color:var(--pico-ink-2)]">
              这里只保存浏览器草稿，不保存密钥，也不会伪造服务端已连接状态。
            </p>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block">
              <span className="mb-1 block text-[12px] text-[color:var(--pico-ink-2)]">
                配置名称
              </span>
              <input
                value={label}
                onChange={(event) => setLabel(event.target.value)}
                placeholder={`例如：${item.name}默认配置`}
                className="pico-field h-9 w-full px-3 text-[13px] outline-none"
              />
            </label>
            <label className="block">
              <span className="mb-1 block text-[12px] text-[color:var(--pico-ink-2)]">
                服务地址或资源标识
              </span>
              <input
                value={endpoint}
                onChange={(event) => setEndpoint(event.target.value)}
                placeholder="https:// 或资源 ID"
                className="pico-field h-9 w-full px-3 text-[13px] outline-none"
              />
            </label>
          </div>
          <label className="mt-3 block">
            <span className="mb-1 block text-[12px] text-[color:var(--pico-ink-2)]">授权范围</span>
            <textarea
              value={scope}
              onChange={(event) => setScope(event.target.value)}
              rows={3}
              className="pico-field w-full resize-none px-3 py-2 text-[13px] outline-none"
            />
          </label>
          <button
            type="button"
            onClick={saveDraft}
            className="pico-chip mt-3 inline-flex items-center gap-1.5 px-3 py-2 text-[12.5px] font-medium"
          >
            <PicoIcon name={saved ? 'check' : 'file'} size="sm" />
            {saved ? '草稿已保存' : '保存配置草稿'}
          </button>
        </div>

        <div className="flex gap-2">
          <button
            type="button"
            disabled={item.status !== 'ready'}
            onClick={useConnector}
            className="pico-cta-accent px-4 py-2.5 text-[13px] font-medium disabled:opacity-40"
          >
            {connectorId === 'school-kb' ? '查看学校材料' : '未接通'}
          </button>
          <button
            type="button"
            onClick={() => navigate('/capability?tab=connectors')}
            className="pico-chip px-4 py-2.5 text-[13px]"
          >
            返回能力中心
          </button>
        </div>
      </div>
    </WorkbenchShell>
  );
}
