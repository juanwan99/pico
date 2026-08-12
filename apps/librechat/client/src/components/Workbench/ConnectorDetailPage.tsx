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
    scope: '只读检索 · 授权后启用',
    note: '可保存索引范围草稿；实际授权与向量索引需要服务端连接器。',
  },
  c5: {
    name: '腾讯文档',
    desc: '文档授权连接',
    status: 'add',
    scope: '指定目录只读 · 写入需逐次确认',
    note: '浏览器版保留配置与权限说明；OAuth 授权需要服务端回调。',
  },
};

export default function ConnectorDetailPage() {
  const { connectorId } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const provider = params.get('provider');
  const projectId = params.get('projectId');
  const returnTo = params.get('return');
  const item = useMemo(() => {
    const base = CATALOG[connectorId || ''] || {
      name: '未知连接器',
      desc: '',
      status: 'add' as const,
      scope: '—',
      note: '未在目录中。',
    };
    if (connectorId === 'c4' && provider) {
      return {
        ...base,
        name: provider === 'lexiang' ? '乐享知识库' : 'ima知识库',
      };
    }
    return base;
  }, [connectorId, provider]);
  const storageKey = `pico:connectorDraft:${connectorId || 'unknown'}:${provider || 'default'}`;
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
    if (projectId && returnTo) {
      try {
        const key = `pico:projectBindings:${projectId}`;
        const current = JSON.parse(localStorage.getItem(key) || '{}') as Record<string, string>;
        localStorage.setItem(key, JSON.stringify({ ...current, connector: item.name }));
      } catch {
        /* navigation still works */
      }
      navigate(returnTo);
      return;
    }
    try {
      sessionStorage.setItem('pico:pendingConnector', item.name);
      sessionStorage.setItem(
        'pico:pendingPrompt',
        `请在允许的权限范围内使用「${item.name}」连接器协助完成任务：`,
      );
    } catch {
      /* ignore */
    }
    navigate('/c/new');
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
                {item.status === 'ready' ? '可用（受限）' : '待服务端授权'}
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
                placeholder={connectorId === 'c3' ? '邮箱账号标识' : 'https:// 或资源 ID'}
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
            {projectId ? '绑定到项目' : '在任务中使用'}
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
