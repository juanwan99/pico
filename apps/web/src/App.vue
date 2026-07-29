<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";

type TimelineItem = {
  kind: "system" | "user" | "assistant" | "tool" | "deny" | "status";
  text: string;
  seq?: number;
};

type TaskItem = { id: string; title: string; created_at?: string };
type ChangeItem = {
  id: string;
  title: string;
  summary: string;
  status: string;
  confirmed_by?: string | null;
  audit?: unknown[];
};

const DEMO_PROMPTS = [
  "列出我学校的班级，并一句话总结。",
  "用工具查班级后，说明一共几个班。",
  "请 echo 一句：pico-proto-ok",
];

const token = ref(localStorage.getItem("pico_token") || "");
const schoolId = ref(localStorage.getItem("pico_school") || "school-a");
const membershipId = ref(localStorage.getItem("pico_member") || "member-1");
const prompt = ref(DEMO_PROMPTS[0]);
const messages = ref<TimelineItem[]>([
  {
    kind: "system",
    text: "Pico 独立原型 · Claude 式三区 AI 空间。密钥仅服务端 · Kimi Agent 多步工具 · 唯一 AI 账本。",
  },
]);
const safety = ref("…");
const freeze = ref("…");
const artifact = ref("");
const busy = ref(false);
const apiOnline = ref(false);
const tasks = ref<TaskItem[]>([]);
const changes = ref<ChangeItem[]>([]);
const activeTaskId = ref<string | null>(null);
const activeRunId = ref<string | null>(null);
const runStatus = ref<string>("—");
const errorBanner = ref("");
const timelineEl = ref<HTMLElement | null>(null);

const principalLabel = computed(() =>
  token.value ? `${schoolId.value} / ${membershipId.value}` : "未签发",
);

const pendingChanges = computed(() =>
  changes.value.filter((c) => c.status === "proposed"),
);

const statusTone = computed(() => {
  const s = runStatus.value;
  if (s === "succeeded") return "ok";
  if (s === "failed" || s === "cancelled") return "bad";
  if (s === "running" || s === "queued") return "run";
  return "";
});

function authHeaders(json = true): Headers {
  const h = new Headers();
  if (token.value) h.set("Authorization", `Bearer ${token.value}`);
  if (json) h.set("Content-Type", "application/json");
  return h;
}

async function api(path: string, init: RequestInit = {}) {
  const headers = authHeaders(!(init.body instanceof FormData));
  if (init.headers) {
    const extra = new Headers(init.headers);
    extra.forEach((v, k) => headers.set(k, v));
  }
  const res = await fetch(path, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data?.detail;
    const msg =
      typeof d === "string"
        ? d
        : d?.message || d?.code || res.statusText || "request failed";
    throw new Error(msg);
  }
  return data;
}

async function scrollTimeline() {
  await nextTick();
  const el = timelineEl.value;
  if (el) el.scrollTop = el.scrollHeight;
}

watch(messages, () => {
  void scrollTimeline();
}, { deep: true });

async function refreshMeta() {
  errorBanner.value = "";
  try {
    await api("/health");
    apiOnline.value = true;
  } catch {
    apiOnline.value = false;
    safety.value = "API offline";
    freeze.value = "—";
    errorBanner.value = "API 未连通。请先 make api（:8000），再刷新。";
    return;
  }
  try {
    const s = await api("/v1/meta/agent-safety");
    safety.value = s.proof?.dangerous_off ? "危险工具 OFF" : "SAFETY FAIL";
  } catch {
    safety.value = "safety n/a";
  }
  try {
    const f = await api("/v1/meta/freeze");
    const pins = f.agent_pins || {};
    freeze.value = `Kimi sdk ${pins["kimi-agent-sdk"]} · cli ${pins["kimi-cli"]}`;
  } catch {
    freeze.value = "freeze n/a";
  }
}

async function mintToken() {
  busy.value = true;
  errorBanner.value = "";
  try {
    const data = await api("/v1/dev/token", {
      method: "POST",
      body: JSON.stringify({
        school_id: schoolId.value,
        membership_id: membershipId.value,
      }),
    });
    token.value = data.access_token;
    localStorage.setItem("pico_token", token.value);
    localStorage.setItem("pico_school", schoolId.value);
    localStorage.setItem("pico_member", membershipId.value);
    messages.value.push({
      kind: "system",
      text: `S4 测试凭证已签发 · ${schoolId.value} / ${membershipId.value}`,
    });
    await refreshTasks();
    await refreshChanges();
  } catch (e) {
    errorBanner.value = `签发失败: ${String(e)}`;
    messages.value.push({ kind: "system", text: errorBanner.value });
  } finally {
    busy.value = false;
  }
}

async function ensureToken() {
  if (!token.value) await mintToken();
}

async function refreshTasks() {
  if (!token.value) return;
  const data = await api("/v1/tasks");
  tasks.value = data.tasks || [];
}

async function refreshChanges() {
  if (!token.value) return;
  const data = await api("/v1/changes");
  changes.value = data.changes || [];
}

function pushEventToTimeline(ev: {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}) {
  const p = ev.payload || {};
  if (ev.type === "message.delta" || ev.type === "message.final") {
    const text = String(p.text || "");
    if (!text) return;
    // merge consecutive assistant deltas
    const last = messages.value[messages.value.length - 1];
    if (last?.kind === "assistant" && ev.type === "message.delta") {
      last.text = text;
      last.seq = ev.seq;
    } else {
      messages.value.push({ kind: "assistant", text, seq: ev.seq });
    }
  } else if (ev.type === "tool.call") {
    messages.value.push({
      kind: "tool",
      text: `调用 ${p.tool}\n${JSON.stringify(p.arguments || {}, null, 2)}`,
      seq: ev.seq,
    });
  } else if (ev.type === "tool.result") {
    messages.value.push({
      kind: "tool",
      text: p.ok
        ? `结果 ${p.tool} ✓\n${JSON.stringify(p.result, null, 2)}`
        : `失败 ${p.tool} · ${p.code}: ${p.message}`,
      seq: ev.seq,
    });
  } else if (ev.type === "auth.deny") {
    messages.value.push({
      kind: "deny",
      text: `跨校拒绝 · ${p.code}\n${p.message}`,
      seq: ev.seq,
    });
  } else if (ev.type === "run.status") {
    runStatus.value = String(p.status || "");
    messages.value.push({
      kind: "status",
      text: `状态 → ${p.status}${p.reason ? ` · ${p.reason}` : ""}`,
      seq: ev.seq,
    });
  } else if (ev.type === "artifact.created") {
    messages.value.push({
      kind: "system",
      text: `产物就绪：${p.title}`,
      seq: ev.seq,
    });
  } else if (ev.type === "change.proposed") {
    messages.value.push({
      kind: "system",
      text: `待确认提案：${p.title}`,
      seq: ev.seq,
    });
  } else if (ev.type === "agent.step") {
    messages.value.push({
      kind: "status",
      text: `步骤 ${p.step}${p.phase ? ` · ${p.phase}` : ""}${p.message ? ` · ${p.message}` : ""}`,
      seq: ev.seq,
    });
  }
}

async function finishArtifacts() {
  if (activeTaskId.value) {
    const t = await api(`/v1/tasks/${activeTaskId.value}`);
    const arts = t.artifacts || [];
    if (arts.length) {
      artifact.value = arts
        .map((a: { title: string; inline: string }) => `# ${a.title}\n\n${a.inline}`)
        .join("\n\n---\n\n");
    }
  }
  await refreshChanges();
}

async function pollRun(runId: string) {
  const seen = new Set<number>();
  let done = false;
  while (!done) {
    const data = await api(`/v1/runs/${runId}/events`);
    for (const ev of data.events || []) {
      if (seen.has(ev.seq)) continue;
      seen.add(ev.seq);
      pushEventToTimeline(ev);
    }
    const runData = await api(`/v1/runs/${runId}`);
    const st = runData.run?.status;
    runStatus.value = st;
    if (st === "succeeded" || st === "failed" || st === "cancelled") {
      done = true;
      break;
    }
    await new Promise((r) => setTimeout(r, 320));
  }
  await finishArtifacts();
}

async function startTask() {
  await ensureToken();
  if (!token.value) return;
  busy.value = true;
  errorBanner.value = "";
  messages.value.push({ kind: "user", text: prompt.value });
  try {
    const data = await api("/v1/tasks", {
      method: "POST",
      body: JSON.stringify({
        title: prompt.value.slice(0, 48),
        prompt: prompt.value,
      }),
    });
    activeTaskId.value = data.task.id;
    activeRunId.value = data.run.id;
    runStatus.value = data.run.status;
    await refreshTasks();
    await pollRun(data.run.id);
  } catch (e) {
    errorBanner.value = `任务失败: ${String(e)}`;
    messages.value.push({ kind: "system", text: errorBanner.value });
  } finally {
    busy.value = false;
  }
}

async function cancelActive() {
  if (!activeRunId.value) return;
  try {
    await api(`/v1/runs/${activeRunId.value}/cancel`, {
      method: "POST",
      body: "{}",
    });
    messages.value.push({ kind: "system", text: "已请求取消 Run" });
  } catch (e) {
    messages.value.push({ kind: "system", text: `取消失败: ${String(e)}` });
  }
}

async function crossSchoolDemo() {
  await ensureToken();
  busy.value = true;
  try {
    const data = await api("/v1/demo/cross-school-deny", {
      method: "POST",
      body: "{}",
    });
    activeTaskId.value = data.task_id;
    activeRunId.value = data.run_id;
    messages.value.push({
      kind: "system",
      text: `S6 跨校演示 · denied=${data.denied}`,
    });
    for (const ev of data.events || []) {
      pushEventToTimeline(ev);
    }
    await refreshTasks();
  } catch (e) {
    messages.value.push({ kind: "system", text: `跨校演示失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function proposeChange() {
  await ensureToken();
  busy.value = true;
  try {
    const data = await api("/v1/changes", {
      method: "POST",
      body: JSON.stringify({
        title: "调整一年级分班（提案）",
        summary: "独立原型：确认只写审计，不写学校业务库。",
        payload: { action: "reassign_class", class_id: "cls-a1" },
        task_id: activeTaskId.value,
        run_id: activeRunId.value,
      }),
    });
    messages.value.push({
      kind: "system",
      text: `S7 提案已创建 · ${data.change.id.slice(0, 8)}…`,
    });
    await refreshChanges();
  } catch (e) {
    messages.value.push({ kind: "system", text: `提案失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function confirmChange(id: string) {
  busy.value = true;
  try {
    const data = await api(`/v1/changes/${id}/confirm`, {
      method: "POST",
      body: "{}",
    });
    messages.value.push({
      kind: "system",
      text: `已人工确认 · 审计已记 · 确认≠写学校库`,
    });
    const block = `\n\n## 审计快照\n\n\`\`\`json\n${JSON.stringify(data.change, null, 2)}\n\`\`\``;
    artifact.value = (artifact.value || "# 产物") + block;
    await refreshChanges();
  } catch (e) {
    messages.value.push({ kind: "system", text: `确认失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function selectTask(id: string) {
  activeTaskId.value = id;
  const t = await api(`/v1/tasks/${id}`);
  const arts = t.artifacts || [];
  artifact.value = arts.length
    ? arts
        .map((a: { title: string; inline: string }) => `# ${a.title}\n\n${a.inline}`)
        .join("\n\n")
    : "此任务暂无产物。";
}

function useDemoPrompt(p: string) {
  prompt.value = p;
}

function clearTimeline() {
  messages.value = [
    {
      kind: "system",
      text: "时间线已清空。可继续创建任务。",
    },
  ];
  runStatus.value = "—";
}

async function runQuickDemo() {
  await ensureToken();
  prompt.value = DEMO_PROMPTS[0];
  await startTask();
  if (runStatus.value === "succeeded") {
    await crossSchoolDemo();
    await proposeChange();
  }
}

onMounted(async () => {
  const q = new URLSearchParams(window.location.search);
  const qTok = q.get("token");
  if (qTok) {
    token.value = qTok;
    localStorage.setItem("pico_token", qTok);
    window.history.replaceState({}, "", window.location.pathname);
  }
  await refreshMeta();
  if (token.value) {
    try {
      await refreshTasks();
      await refreshChanges();
    } catch {
      token.value = "";
      localStorage.removeItem("pico_token");
    }
  }
});
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <div class="rail-brand">
        <div class="logo">P</div>
        <div>
          <div class="logo-title">Pico</div>
          <div class="muted tiny">独立 AI 底座原型</div>
        </div>
      </div>

      <div class="section">
        <div class="section-head">
          <h2>任务</h2>
          <button class="ghost tiny-btn" :disabled="busy" @click="refreshTasks">刷新</button>
        </div>
        <ul class="list">
          <li
            v-for="t in tasks"
            :key="t.id"
            :class="{ active: t.id === activeTaskId }"
            @click="selectTask(t.id)"
          >
            <span class="task-title">{{ t.title }}</span>
          </li>
          <li v-if="!tasks.length" class="muted empty">签发后创建任务会出现在这里</li>
        </ul>
      </div>

      <div class="section">
        <h2>身份 (S4)</h2>
        <label class="field-label">school_id</label>
        <input v-model="schoolId" placeholder="school-a" />
        <label class="field-label">membership_id</label>
        <input v-model="membershipId" placeholder="member-1" />
        <button class="block" :disabled="busy" @click="mintToken">签发测试凭证</button>
        <p class="muted tiny">claim 形状预留对接；原型用测试签发器</p>
      </div>

      <div class="section">
        <div class="section-head">
          <h2>待确认 (S7)</h2>
          <span v-if="pendingChanges.length" class="badge">{{ pendingChanges.length }}</span>
        </div>
        <ul class="list">
          <li v-for="c in changes" :key="c.id" class="change-item">
            <div class="task-title">{{ c.title }}</div>
            <div class="muted tiny">{{ c.status }}</div>
            <button
              v-if="c.status === 'proposed'"
              class="primary block sm"
              :disabled="busy"
              @click="confirmChange(c.id)"
            >
              人工确认
            </button>
          </li>
          <li v-if="!changes.length" class="muted empty">无提案</li>
        </ul>
        <button class="block" :disabled="busy" @click="proposeChange">新建提案</button>
      </div>
    </aside>

    <section class="main">
      <header class="main-header">
        <div>
          <div class="brand">AI 空间 <span>Claude 式三区 · 今日原型</span></div>
          <div class="muted tiny">唯一 AI 账本 · FakeEdu · 无 edu 联调</div>
        </div>
        <div class="row wrap">
          <span class="pill" :class="apiOnline ? 'ok' : 'bad'">{{
            apiOnline ? "API 在线" : "API 离线"
          }}</span>
          <span class="pill" :class="safety.includes('OFF') ? 'ok' : 'bad'">{{
            safety
          }}</span>
          <span class="pill">{{ freeze }}</span>
          <span class="pill" :class="statusTone">run · {{ runStatus }}</span>
          <span class="pill">{{ principalLabel }}</span>
        </div>
      </header>

      <div v-if="errorBanner" class="banner error">{{ errorBanner }}</div>

      <div class="demo-bar">
        <span class="muted tiny">演示提示词</span>
        <button
          v-for="p in DEMO_PROMPTS"
          :key="p"
          class="chip"
          type="button"
          @click="useDemoPrompt(p)"
        >
          {{ p.slice(0, 18) }}…
        </button>
        <button class="chip accent" type="button" :disabled="busy" @click="runQuickDemo">
          一键演示路径
        </button>
        <button class="chip" type="button" @click="clearTimeline">清空时间线</button>
      </div>

      <div ref="timelineEl" class="timeline">
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="bubble"
          :class="m.kind"
        >
          <div class="bubble-label">{{ m.kind }}</div>
          <pre class="bubble-body">{{ m.text }}</pre>
        </div>
      </div>

      <div class="composer">
        <textarea
          v-model="prompt"
          rows="3"
          placeholder="描述要交办的事… 例如：列出我学校的班级"
          @keydown.meta.enter.prevent="startTask"
          @keydown.ctrl.enter.prevent="startTask"
        />
        <div class="row wrap">
          <button class="primary" :disabled="busy" @click="startTask">
            {{ busy ? "运行中…" : "创建任务并运行" }}
          </button>
          <button :disabled="busy || !activeRunId" @click="cancelActive">取消 Run</button>
          <button :disabled="busy" @click="crossSchoolDemo">跨校拒绝 (S6)</button>
          <button :disabled="busy" @click="refreshMeta">刷新状态</button>
        </div>
        <p class="muted tiny">
          ⌘/Ctrl+Enter 发送 · Shell/File/Web/MCP 关闭 · 确认≠写学校库
        </p>
      </div>
    </section>

    <aside class="artifacts">
      <div class="section-head">
        <h2>产物</h2>
        <span class="muted tiny">Artifact</span>
      </div>
      <div v-if="!artifact" class="empty-art">
        <p>工具成功后，班级表 / 报告会出现在这里。</p>
        <p class="muted tiny">建议先跑「列出我学校的班级」。</p>
      </div>
      <pre v-else class="art-body">{{ artifact }}</pre>
    </aside>
  </div>
</template>
