import { AlertCircle, CheckCircle2, Circle, FileText, Wrench } from 'lucide-react';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';
import { workbenchToolResultLine, workbenchToolStepLine } from '~/utils/picoWorkbenchProgress';

const VISIBLE_EVENT_TYPES = new Set([
  'skill.snapshot',
  'skill.unknown',
  'tool.call',
  'tool.result',
  'search.sources',
  'sandbox.session',
  'artifact.created',
  'agent.step',
  'run.status',
  'run.error',
]);

function textValue(payload: Record<string, unknown>, ...keys: string[]): string | null {
  for (const key of keys) {
    const value = payload[key];
    if (typeof value === 'string' && value.trim()) {
      return value.trim();
    }
  }
  return null;
}

export function describePicoRunEvent(
  event: PicoRunEvent,
  runSucceeded = false,
): {
  title: string;
  detail: string | null;
} {
  const payload = event.payload || {};
  if (event.type === 'skill.snapshot') {
    const skill = textValue(payload, 'name', 'id', 'skill_id') || '已选择 Skill';
    const tools = Array.isArray(payload.tools)
      ? payload.tools.filter((tool): tool is string => typeof tool === 'string' && Boolean(tool))
      : [];
    return {
      title: `Skill · ${skill}`,
      detail: tools.length ? `工具：${tools.join('、')}` : '无工具',
    };
  }
  if (event.type === 'skill.unknown') {
    return {
      title: '未知 Skill',
      detail: textValue(payload, 'skill_id', 'id', 'name'),
    };
  }
  if (event.type === 'tool.call') {
    const tool = textValue(payload, 'tool', 'name') || '';
    const step = textValue(payload, 'step_line') || workbenchToolStepLine(tool);
    return {
      title: step || '正在调工具',
      detail: null,
    };
  }
  if (event.type === 'tool.result') {
    const ok = payload.ok !== false;
    const tool = textValue(payload, 'tool', 'name') || '';
    const code = textValue(payload, 'code', 'error_code');
    const userMessage = textValue(payload, 'user_message');
    // P2 status-truth: a tool step that failed but the run still succeeded was
    // recovered — label it as such instead of a bare red-ish「失败」that
    // contradicts the terminal success.
    const detail = ok
      ? '成功'
      : runSucceeded
        ? '失败 · 已恢复'
        : [userMessage || '失败', code && !userMessage ? `错误码：${code}` : null]
            .filter(Boolean)
            .join(' · ');
    return {
      title: workbenchToolResultLine(tool, ok),
      detail,
    };
  }
  if (event.type === 'sandbox.session') {
    const url = textValue(payload, 'url');
    const title = textValue(payload, 'title');
    return {
      title: '隔离网页已打开',
      detail: [title, url].filter(Boolean).join(' · ') || '请在结果区「网页」里点、自己登录',
    };
  }
  if (event.type === 'search.sources') {
    const sources = Array.isArray(payload.sources) ? payload.sources : [];
    const links = sources
      .map((item) => {
        if (!item || typeof item !== 'object') {
          return null;
        }
        const row = item as { title?: unknown; url?: unknown };
        const url = typeof row.url === 'string' ? row.url.trim() : '';
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
          return null;
        }
        const title = typeof row.title === 'string' && row.title.trim() ? row.title.trim() : url;
        return { title, url };
      })
      .filter((item): item is { title: string; url: string } => Boolean(item));
    if (links.length === 0 || payload.honest_miss === true) {
      return { title: '来源', detail: '未检索到可用来源' };
    }
    return {
      title: `来源 · ${links.length} 条`,
      detail: links.map((item) => item.title).join(' · '),
    };
  }
  if (event.type === 'agent.step') {
    const phase = textValue(payload, 'phase', 'name') || '步骤';
    const n = payload.n ?? payload.step ?? payload.index;
    const stepLabel = typeof n === 'number' || typeof n === 'string' ? ` #${n}` : '';
    return {
      title: `智能体步骤${stepLabel}`,
      detail: phase,
    };
  }
  if (event.type === 'run.error') {
    return {
      title: '运行出错',
      detail:
        textValue(payload, 'user_message', 'message', 'reason') || '本次运行未能完成，请稍后重试。',
    };
  }
  if (event.type === 'run.status') {
    const status = textValue(payload, 'status');
    const code = textValue(payload, 'code', 'error_code');
    const runtime = textValue(payload, 'runtime');
    const runtimeLabel = runtime === 'kimi-agent' ? 'Kimi Agent' : runtime ? runtime : null;
    if (status === 'running' || status === 'queued' || status === 'preparing') {
      return {
        title: status === 'running' ? '正在运行' : '排队中',
        detail: runtimeLabel ? `运行时 · ${runtimeLabel}` : null,
      };
    }
    if (status === 'succeeded') {
      return {
        title: '运行成功',
        detail: runtimeLabel ? `运行时 · ${runtimeLabel}` : null,
      };
    }
    if (status === 'failed') {
      return {
        title: '运行失败',
        detail: [
          textValue(payload, 'user_message') || '本次运行未能完成，请稍后重试。',
          runtimeLabel ? `运行时 · ${runtimeLabel}` : null,
          code ? `错误码：${code}` : null,
        ]
          .filter(Boolean)
          .join(' · '),
      };
    }
    if (status === 'cancelled') {
      return {
        title: '云端任务已停止',
        detail: [
          textValue(payload, 'user_message') ||
            (code ? `任务已取消 · 错误码：${code}` : '任务栏「停止任务」已取消云端执行'),
          runtimeLabel ? `运行时 · ${runtimeLabel}` : null,
        ]
          .filter(Boolean)
          .join(' · '),
      };
    }
  }
  if (event.type === 'artifact.created') {
    return {
      title: `生成产物 · ${textValue(payload, 'title', 'name') || '未命名产物'}`,
      detail: textValue(payload, 'kind'),
    };
  }
  return { title: event.type, detail: null };
}

function searchSourceLinks(event: PicoRunEvent): { title: string; url: string }[] {
  if (event.type !== 'search.sources') {
    return [];
  }
  const sources = Array.isArray(event.payload?.sources) ? event.payload.sources : [];
  const links: { title: string; url: string }[] = [];
  for (const item of sources) {
    if (!item || typeof item !== 'object') {
      continue;
    }
    const row = item as { title?: unknown; url?: unknown };
    const url = typeof row.url === 'string' ? row.url.trim() : '';
    if (!url.startsWith('http://') && !url.startsWith('https://')) {
      continue;
    }
    const title = typeof row.title === 'string' && row.title.trim() ? row.title.trim() : url;
    links.push({ title, url });
  }
  return links;
}

function EventIcon({ type }: { type: string }) {
  if (type === 'run.status' || type === 'run.error') {
    return <AlertCircle className="h-3.5 w-3.5" />;
  }
  if (type === 'agent.step') {
    return <Circle className="h-3.5 w-3.5" />;
  }
  if (type === 'tool.call' || type === 'tool.result') {
    return <Wrench className="h-3.5 w-3.5" />;
  }
  if (type === 'artifact.created') {
    return <FileText className="h-3.5 w-3.5" />;
  }
  if (type === 'skill.snapshot') {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  return <Circle className="h-3.5 w-3.5" />;
}

export default function RunTimeline({
  events,
  run,
}: {
  events?: PicoRunEvent[] | null;
  run?: PicoRun | null;
}) {
  const allEvents = events || [];
  const visible = allEvents
    .filter((event) => {
      if (!VISIBLE_EVENT_TYPES.has(event.type)) {
        return false;
      }
      if (event.type !== 'run.status') {
        return true;
      }
      return ['queued', 'preparing', 'running', 'succeeded', 'failed', 'cancelled'].includes(
        String(event.payload?.status || ''),
      );
    })
    .sort((a, b) => a.seq - b.seq);
  const terminalStatus =
    run?.status === 'failed' || run?.status === 'cancelled' ? run.status : null;
  const hasTerminalEvent = visible.some(
    (event) => event.type === 'run.status' && event.payload?.status === terminalStatus,
  );
  if (terminalStatus && run && !hasTerminalEvent) {
    visible.push({
      id: `${run.id}-terminal-status`,
      run_id: run.id,
      seq: Math.max(0, ...allEvents.map((event) => event.seq)) + 1,
      type: 'run.status',
      payload: { status: terminalStatus },
    });
  }

  // P2-E4 badge truth: recover whether the run ended successfully from the run
  // object OR the run's own terminal event. Some surfaces render a timeline
  // without the `run` prop (e.g. the automation page); deriving success from
  // the event stream keeps recovered tool steps labeled 「失败 · 已恢复」 instead
  // of a bare 「失败」 that contradicts the terminal success.
  const runSucceeded =
    run?.status === 'succeeded' ||
    allEvents.some(
      (event) => event.type === 'run.status' && event.payload?.status === 'succeeded',
    );

  return (
    <section className="mb-3" aria-label="执行步骤">
      <p className="mb-2 text-[12px] font-medium text-[#8c8c8c]">执行步骤</p>
      {visible.length === 0 ? (
        <p className="rounded-lg bg-[#fafafa] px-3 py-2 text-[12px] text-[#8c8c8c] dark:bg-surface-tertiary">
          暂无步骤
        </p>
      ) : (
        <ol className="space-y-1.5">
          {visible.map((event) => {
            const description = describePicoRunEvent(event, runSucceeded);
            const links = searchSourceLinks(event);
            return (
              <li
                key={event.id}
                className="flex gap-2 rounded-lg border border-black/[0.05] bg-[#fafafa] px-2.5 py-2 dark:border-border-light dark:bg-surface-tertiary"
              >
                <span className="mt-0.5 text-[#6b6b6b]" aria-hidden="true">
                  <EventIcon type={event.type} />
                </span>
                <div className="min-w-0">
                  <p className="truncate text-[12px] font-medium">{description.title}</p>
                  {links.length > 0 ? (
                    <ul className="mt-0.5 space-y-0.5">
                      {links.map((link) => (
                        <li key={link.url}>
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block truncate text-[11px] text-[#3b6fd9] underline-offset-2 hover:underline"
                            data-testid="pico-timeline-source-link"
                          >
                            {link.title}
                          </a>
                        </li>
                      ))}
                    </ul>
                  ) : description.detail ? (
                    <p className="mt-0.5 truncate text-[11px] text-[#8c8c8c]">
                      {description.detail}
                    </p>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}
