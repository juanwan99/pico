import { AlertCircle, CheckCircle2, Circle, FileText, Wrench } from 'lucide-react';
import type { PicoRun, PicoRunEvent } from '~/data-provider/pico/api';

const VISIBLE_EVENT_TYPES = new Set([
  'skill.snapshot',
  'skill.unknown',
  'tool.call',
  'tool.result',
  'artifact.created',
  'run.status',
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

export function describePicoRunEvent(event: PicoRunEvent): {
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
    return {
      title: `调用工具 · ${textValue(payload, 'tool', 'name') || '未命名工具'}`,
      detail: null,
    };
  }
  if (event.type === 'tool.result') {
    const ok = payload.ok !== false;
    const code = textValue(payload, 'code', 'error_code');
    return {
      title: `工具结果 · ${textValue(payload, 'tool', 'name') || '未命名工具'}`,
      detail: ok ? '成功' : ['失败', code ? `错误码：${code}` : null].filter(Boolean).join(' · '),
    };
  }
  if (event.type === 'run.status') {
    const status = textValue(payload, 'status');
    const code = textValue(payload, 'code', 'error_code');
    if (status === 'failed') {
      return {
        title: '运行失败',
        detail: [
          textValue(payload, 'user_message') || '本次运行未能完成，请稍后重试。',
          code ? `错误码：${code}` : null,
        ]
          .filter(Boolean)
          .join(' · '),
      };
    }
    if (status === 'cancelled') {
      return {
        title: '运行已取消',
        detail: code ? `已停止生成 · 错误码：${code}` : '已停止生成',
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

function EventIcon({ type }: { type: string }) {
  if (type === 'run.status') {
    return <AlertCircle className="h-3.5 w-3.5" />;
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
      return ['failed', 'cancelled'].includes(String(event.payload?.status || ''));
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
            const description = describePicoRunEvent(event);
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
                  {description.detail ? (
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
