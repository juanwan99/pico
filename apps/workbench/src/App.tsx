import { useCallback, useEffect, useRef, useState } from "react";
import {
  Plus,
  Bot,
  FolderKanban,
  Puzzle,
  Zap,
  MoreHorizontal,
  Search,
  Bell,
  Paperclip,
  Mic,
  ArrowUp,
  FileText,
  BarChart3,
  Presentation,
  BookOpen,
  GraduationCap,
  Sparkles,
  ChevronDown,
  Home,
  MessageSquare,
  Settings2,
  Shield,
} from "lucide-react";

type Mode = "office" | "teach" | "data";
type View = "home" | "chat" | "assistants" | "projects" | "skills" | "auto";

type Msg = { id: string; role: "user" | "assistant" | "system"; content: string };

const MODES: { id: Mode; label: string }[] = [
  { id: "office", label: "日常办公" },
  { id: "teach", label: "教学教研" },
  { id: "data", label: "数据分析" },
];

const CHIPS: Record<Mode, { icon: React.ReactNode; label: string; prompt: string }[]> = {
  office: [
    { icon: <FileText size={14} />, label: "文档处理", prompt: "帮我整理一份会议纪要模板，适合学校行政场景。" },
    { icon: <Presentation size={14} />, label: "幻灯片", prompt: "帮我做一页家长会开场 PPT 大纲。" },
    { icon: <BarChart3 size={14} />, label: "数据可视化", prompt: "把班级成绩分布用文字描述成图表方案。" },
    { icon: <BookOpen size={14} />, label: "深度研究", prompt: "用要点总结「形成性评价」的核心做法。" },
    { icon: <Sparkles size={14} />, label: "通知起草", prompt: "起草一份期末考试安排的家长通知（温和专业）。" },
    { icon: <GraduationCap size={14} />, label: "教案辅助", prompt: "给初中数学「一元一次方程」写 15 分钟引入环节。" },
  ],
  teach: [
    { icon: <GraduationCap size={14} />, label: "教案设计", prompt: "设计一节 40 分钟高一语文课的三维目标与活动。" },
    { icon: <FileText size={14} />, label: "作业批改建议", prompt: "如何高效批改作文并给出可操作评语？" },
    { icon: <BookOpen size={14} />, label: "学情分析", prompt: "根据一次单元测的薄弱点，给出分层辅导建议。" },
    { icon: <Presentation size={14} />, label: "公开课提纲", prompt: "生成公开课听评课观察量表要点。" },
  ],
  data: [
    { icon: <BarChart3 size={14} />, label: "成绩分析", prompt: "给我一套班级成绩分析的标准步骤与指标。" },
    { icon: <FileText size={14} />, label: "报表模板", prompt: "输出「月度教学常规检查」数据表字段设计。" },
    { icon: <Sparkles size={14} />, label: "异常排查", prompt: "某科均分骤降，应如何排查原因？" },
  ],
};

const NAV: { id: View; label: string; icon: React.ReactNode; primary?: boolean }[] = [
  { id: "home", label: "新建任务", icon: <Plus size={16} />, primary: true },
  { id: "assistants", label: "助理", icon: <Bot size={16} /> },
  { id: "projects", label: "项目", icon: <FolderKanban size={16} /> },
  { id: "skills", label: "专家 · 技能 · 连接器", icon: <Puzzle size={16} /> },
  { id: "auto", label: "自动化", icon: <Zap size={16} /> },
];

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

async function streamChat(
  messages: { role: string; content: string }[],
  onDelta: (t: string) => void,
  signal: AbortSignal,
) {
  const res = await fetch("/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: "Bearer pico-dev",
    },
    body: JSON.stringify({
      model: "moonshot-v1-8k",
      stream: true,
      messages,
    }),
    signal,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || `HTTP ${res.status}`);
  }
  const reader = res.body!.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const lines = buf.split("\n");
    buf = lines.pop() || "";
    for (const line of lines) {
      const s = line.trim();
      if (!s.startsWith("data:")) continue;
      const data = s.slice(5).trim();
      if (data === "[DONE]") return;
      try {
        const j = JSON.parse(data);
        const c = j.choices?.[0]?.delta?.content;
        if (c) onDelta(c);
      } catch {
        /* ignore */
      }
    }
  }
}

export default function App() {
  const [view, setView] = useState<View>("home");
  const [mode, setMode] = useState<Mode>("office");
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState("Auto");
  const abortRef = useRef<AbortController | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const send = useCallback(
    async (text: string) => {
      const prompt = text.trim();
      if (!prompt || busy) return;
      setView("chat");
      setInput("");
      const userMsg: Msg = { id: uid(), role: "user", content: prompt };
      const asstId = uid();
      setMessages((m) => [...m, userMsg, { id: asstId, role: "assistant", content: "" }]);
      setBusy(true);
      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;
      const history = [...messages, userMsg]
        .filter((x) => x.role === "user" || x.role === "assistant")
        .map((x) => ({ role: x.role, content: x.content }))
        .filter((x) => x.content);
      try {
        await streamChat(
          history,
          (delta) => {
            setMessages((m) =>
              m.map((x) => (x.id === asstId ? { ...x, content: x.content + delta } : x)),
            );
          },
          ac.signal,
        );
      } catch (e) {
        if ((e as Error).name === "AbortError") return;
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((m) =>
          m.map((x) =>
            x.id === asstId
              ? { ...x, content: x.content || `【出错】${msg}` }
              : x,
          ),
        );
      } finally {
        setBusy(false);
      }
    },
    [busy, messages],
  );

  const stop = () => {
    abortRef.current?.abort();
    setBusy(false);
  };

  const newTask = () => {
    abortRef.current?.abort();
    setMessages([]);
    setInput("");
    setBusy(false);
    setView("home");
  };

  return (
    <div className="flex h-full bg-white text-[14px]">
      {/* Sidebar — WorkBuddy IA */}
      <aside className="flex w-[220px] shrink-0 flex-col border-r border-[var(--color-pico-line)] bg-[var(--color-pico-panel)]">
        <div className="flex items-center gap-2 px-4 pb-3 pt-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[var(--color-pico-accent)] text-sm font-bold text-white shadow-sm">
            P
          </div>
          <div className="min-w-0">
            <div className="truncate text-[15px] font-semibold tracking-tight">Pico</div>
            <div className="text-[11px] text-[var(--color-pico-muted)]">AI 工作台 · v0.5</div>
          </div>
        </div>

        <nav className="flex flex-1 flex-col gap-0.5 px-2">
          {NAV.map((item) => {
            const active =
              item.id === "home"
                ? view === "home" || view === "chat"
                : view === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => (item.id === "home" ? newTask() : setView(item.id))}
                className={[
                  "flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition",
                  active
                    ? "bg-white font-medium text-[var(--color-pico-ink)] shadow-sm ring-1 ring-black/5"
                    : "text-zinc-600 hover:bg-white/70",
                  item.primary && active ? "ring-emerald-500/20" : "",
                ].join(" ")}
              >
                <span
                  className={[
                    "flex h-7 w-7 items-center justify-center rounded-lg",
                    active ? "bg-[var(--color-pico-accent-soft)] text-emerald-700" : "text-zinc-500",
                  ].join(" ")}
                >
                  {item.icon}
                </span>
                <span className="truncate text-[13px]">{item.label}</span>
              </button>
            );
          })}

          <button
            type="button"
            className="mt-1 flex items-center gap-2.5 rounded-xl px-3 py-2.5 text-left text-zinc-600 hover:bg-white/70"
          >
            <span className="flex h-7 w-7 items-center justify-center rounded-lg text-zinc-500">
              <MoreHorizontal size={16} />
            </span>
            <span className="text-[13px]">更多</span>
            <span className="ml-auto text-[11px] text-zinc-400">资料库</span>
          </button>

          <div className="mt-4 px-3 text-[11px] font-medium uppercase tracking-wide text-zinc-400">
            空间
          </div>
          <button
            type="button"
            className="mt-1 flex items-center gap-2 rounded-xl px-3 py-2 text-left text-[13px] text-zinc-600 hover:bg-white/70"
          >
            <Home size={14} className="text-zinc-400" />
            默认工作区
            <ChevronDown size={14} className="ml-auto text-zinc-400" />
          </button>
          <button
            type="button"
            className="flex items-center gap-2 rounded-xl px-3 py-2 text-left text-[13px] text-emerald-700 hover:bg-white/70"
          >
            <BookOpen size={14} />
            新手指引
          </button>
        </nav>

        <div className="border-t border-[var(--color-pico-line)] p-3">
          <div className="flex items-center gap-2 rounded-xl bg-white px-2 py-2 shadow-sm ring-1 ring-black/5">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-100 text-xs font-semibold text-emerald-800">
              师
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-[13px] font-medium">教师演示账号</div>
              <div className="truncate text-[11px] text-zinc-400">school-a · 本机</div>
            </div>
            <Settings2 size={14} className="text-zinc-400" />
          </div>
        </div>
      </aside>

      {/* Main */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center justify-between border-b border-[var(--color-pico-line)] px-5">
          <div className="flex items-center gap-3 text-zinc-400">
            <Search size={16} />
            <span className="text-[13px]">搜索任务、文件、技能…</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="rounded-full bg-gradient-to-r from-emerald-500 to-teal-500 px-3 py-1.5 text-[12px] font-medium text-white shadow-sm"
            >
              Pico 独立 AI 底座
            </button>
            <button type="button" className="rounded-lg p-2 text-zinc-500 hover:bg-zinc-100">
              <Bell size={16} />
            </button>
          </div>
        </header>

        {view === "home" && (
          <HomePane
            mode={mode}
            setMode={setMode}
            input={input}
            setInput={setInput}
            model={model}
            setModel={setModel}
            onSend={() => send(input)}
            onChip={(p) => send(p)}
          />
        )}

        {view === "chat" && (
          <ChatPane
            messages={messages}
            busy={busy}
            input={input}
            setInput={setInput}
            onSend={() => send(input)}
            onStop={stop}
            onNew={newTask}
            bottomRef={bottomRef}
            model={model}
          />
        )}

        {view === "assistants" && (
          <Placeholder
            title="助理"
            desc="预设角色助理（班主任、教研组长、教务…）。后续接入 Pico 专家配置。"
          />
        )}
        {view === "projects" && (
          <Placeholder title="项目" desc="把多轮任务归档为项目空间，带文件与产物列表。" />
        )}
        {view === "skills" && (
          <Placeholder
            title="专家 · 技能 · 连接器"
            desc="技能白名单与学校连接器入口。底层走 Pico 工具环，Shell/File/Web 默认关闭。"
          />
        )}
        {view === "auto" && (
          <Placeholder title="自动化" desc="定时任务与工作流（Phase 后置）。" />
        )}
      </main>
    </div>
  );
}

function HomePane({
  mode,
  setMode,
  input,
  setInput,
  model,
  setModel,
  onSend,
  onChip,
}: {
  mode: Mode;
  setMode: (m: Mode) => void;
  input: string;
  setInput: (s: string) => void;
  model: string;
  setModel: (s: string) => void;
  onSend: () => void;
  onChip: (p: string) => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center overflow-auto px-6 pb-10 pt-16">
      <h1 className="text-center text-[32px] font-semibold tracking-tight text-zinc-900">
        Pico，我帮你
      </h1>
      <p className="mt-2 text-center text-[14px] text-zinc-500">
        学校场景 AI 工作台 · 一句话开始任务
      </p>

      {/* mode tabs */}
      <div className="mt-7 flex items-center gap-1 rounded-full bg-zinc-100 p-1">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            className={[
              "rounded-full px-4 py-1.5 text-[13px] transition",
              mode === m.id
                ? "bg-zinc-900 font-medium text-white shadow-sm"
                : "text-zinc-600 hover:text-zinc-900",
            ].join(" ")}
          >
            {m.label}
          </button>
        ))}
      </div>

      {/* chips */}
      <div className="mt-6 flex max-w-[720px] flex-wrap items-center justify-center gap-2">
        {CHIPS[mode].map((c) => (
          <button
            key={c.label}
            type="button"
            onClick={() => onChip(c.prompt)}
            className="inline-flex items-center gap-1.5 rounded-full border border-zinc-200 bg-white px-3 py-1.5 text-[12.5px] text-zinc-700 shadow-sm transition hover:border-emerald-300 hover:bg-emerald-50"
          >
            <span className="text-zinc-400">{c.icon}</span>
            {c.label}
          </button>
        ))}
      </div>

      {/* composer card */}
      <div className="mt-8 w-full max-w-[720px] rounded-[20px] border border-zinc-200 bg-white p-4 shadow-[0_8px_30px_rgba(0,0,0,0.04)]">
        <div className="text-[13px] text-zinc-400">
          今天帮你做什么？ <span className="text-zinc-300">@ 引用文件，/ 调用技能与指令</span>
        </div>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              onSend();
            }
          }}
          rows={3}
          placeholder=""
          className="mt-2 w-full resize-none border-0 bg-transparent text-[15px] text-zinc-900 outline-none placeholder:text-zinc-300"
        />
        <div className="mt-2 flex items-center gap-2">
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-zinc-200 text-zinc-500 hover:bg-zinc-50"
            title="附件"
          >
            <Paperclip size={16} />
          </button>
          <div className="flex-1" />
          <button
            type="button"
            onClick={() => setModel(model === "Auto" ? "Kimi" : "Auto")}
            className="inline-flex items-center gap-1 rounded-full border border-zinc-200 px-2.5 py-1 text-[12px] text-zinc-600 hover:bg-zinc-50"
          >
            {model}
            <ChevronDown size={12} />
          </button>
          <button
            type="button"
            className="flex h-9 w-9 items-center justify-center rounded-full border border-zinc-200 text-zinc-500 hover:bg-zinc-50"
          >
            <Mic size={16} />
          </button>
          <button
            type="button"
            onClick={onSend}
            disabled={!input.trim()}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-zinc-900 text-white transition enabled:hover:bg-zinc-800 disabled:opacity-30"
          >
            <ArrowUp size={16} />
          </button>
        </div>
      </div>

      <div className="mt-4 flex items-center gap-3 text-[12px] text-zinc-400">
        <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 px-2.5 py-1">
          <FolderKanban size={12} /> 选择工作空间
          <ChevronDown size={12} />
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-zinc-200 px-2.5 py-1">
          <Shield size={12} /> 默认权限
          <ChevronDown size={12} />
        </span>
      </div>
    </div>
  );
}

function ChatPane({
  messages,
  busy,
  input,
  setInput,
  onSend,
  onStop,
  onNew,
  bottomRef,
  model,
}: {
  messages: Msg[];
  busy: boolean;
  input: string;
  setInput: (s: string) => void;
  onSend: () => void;
  onStop: () => void;
  onNew: () => void;
  bottomRef: React.RefObject<HTMLDivElement | null>;
  model: string;
}) {
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-zinc-100 px-6 py-2">
        <div className="flex items-center gap-2 text-[13px] text-zinc-500">
          <MessageSquare size={14} />
          当前任务
        </div>
        <button
          type="button"
          onClick={onNew}
          className="rounded-lg px-2.5 py-1 text-[12px] text-emerald-700 hover:bg-emerald-50"
        >
          + 新建任务
        </button>
      </div>

      <div className="flex-1 overflow-auto px-6 py-6">
        <div className="mx-auto max-w-[760px] space-y-5">
          {messages.map((m) => (
            <div
              key={m.id}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={[
                  "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-[14.5px] leading-relaxed",
                  m.role === "user"
                    ? "bg-zinc-900 text-white"
                    : "bg-zinc-50 text-zinc-800 ring-1 ring-zinc-100",
                ].join(" ")}
              >
                {m.content || (busy ? "…" : "")}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>
      </div>

      <div className="border-t border-zinc-100 px-6 py-4">
        <div className="mx-auto max-w-[760px] rounded-[18px] border border-zinc-200 bg-white p-3 shadow-sm">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            rows={2}
            placeholder="继续描述任务，或补充约束…"
            className="w-full resize-none border-0 bg-transparent text-[14px] outline-none"
          />
          <div className="mt-1 flex items-center gap-2">
            <span className="text-[11px] text-zinc-400">{model} · 真流式</span>
            <div className="flex-1" />
            {busy ? (
              <button
                type="button"
                onClick={onStop}
                className="rounded-full bg-zinc-200 px-3 py-1.5 text-[12px] font-medium text-zinc-700"
              >
                停止
              </button>
            ) : (
              <button
                type="button"
                onClick={onSend}
                disabled={!input.trim()}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-zinc-900 text-white disabled:opacity-30"
              >
                <ArrowUp size={14} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function Placeholder({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center px-8 text-center">
      <div className="rounded-2xl border border-dashed border-zinc-200 bg-zinc-50 px-10 py-12">
        <h2 className="text-lg font-semibold text-zinc-800">{title}</h2>
        <p className="mt-2 max-w-md text-[13px] leading-relaxed text-zinc-500">{desc}</p>
      </div>
    </div>
  );
}
