<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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

const token = ref(localStorage.getItem("pico_token") || "");
const schoolId = ref(localStorage.getItem("pico_school") || "school-a");
const membershipId = ref(localStorage.getItem("pico_member") || "member-1");
const prompt = ref("列出我学校的班级，并简要说明。");
const messages = ref<TimelineItem[]>([
  {
    kind: "system",
    text: "Pico Phase 1 — 三区 AI 空间。创建任务后服务端多步工具环 + Event 账本流式回放。",
  },
]);
const safety = ref("…");
const freeze = ref("…");
const artifact = ref("产物将在工具成功后出现于此。");
const busy = ref(false);
const tasks = ref<TaskItem[]>([]);
const changes = ref<ChangeItem[]>([]);
const activeTaskId = ref<string | null>(null);
const activeRunId = ref<string | null>(null);
const runStatus = ref<string>("—");

const principalLabel = computed(() =>
  token.value ? `${schoolId.value} / ${membershipId.value}` : "未签发",
);

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

async function refreshMeta() {
  try {
    const s = await api("/v1/meta/agent-safety");
    safety.value = s.proof?.dangerous_off ? "Shell/File/Web/MCP OFF" : "SAFETY FAIL";
  } catch (e) {
    safety.value = `API offline`;
  }
  try {
    const f = await api("/v1/meta/freeze");
    const pins = f.agent_pins || {};
    freeze.value = `sdk ${pins["kimi-agent-sdk"]} · cli ${pins["kimi-cli"]}`;
  } catch {
    freeze.value = "freeze n/a";
  }
}

async function mintToken() {
  busy.value = true;
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
      text: `测试凭证已签发 · school_id=${schoolId.value}`,
    });
    await refreshTasks();
    await refreshChanges();
  } catch (e) {
    messages.value.push({ kind: "system", text: `签发失败: ${String(e)}` });
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
    messages.value.push({
      kind: "assistant",
      text: String(p.text || ""),
      seq: ev.seq,
    });
  } else if (ev.type === "tool.call") {
    messages.value.push({
      kind: "tool",
      text: `→ ${p.tool}(${JSON.stringify(p.arguments || {})})`,
      seq: ev.seq,
    });
  } else if (ev.type === "tool.result") {
    messages.value.push({
      kind: "tool",
      text: p.ok
        ? `← ${p.tool} OK\n${JSON.stringify(p.result, null, 2)}`
        : `← ${p.tool} FAIL ${p.code}: ${p.message}`,
      seq: ev.seq,
    });
  } else if (ev.type === "auth.deny") {
    messages.value.push({
      kind: "deny",
      text: `跨校拒绝 ${p.code}: ${p.message}`,
      seq: ev.seq,
    });
  } else if (ev.type === "run.status") {
    runStatus.value = String(p.status || "");
    messages.value.push({
      kind: "status",
      text: `run.status → ${JSON.stringify(p)}`,
      seq: ev.seq,
    });
  } else if (ev.type === "artifact.created") {
    messages.value.push({
      kind: "system",
      text: `产物已创建: ${p.title}`,
      seq: ev.seq,
    });
  } else if (ev.type === "change.proposed") {
    messages.value.push({
      kind: "system",
      text: `变更提案: ${p.title} (${p.change_id})`,
      seq: ev.seq,
    });
  } else if (ev.type === "agent.step") {
    messages.value.push({
      kind: "status",
      text: `agent step ${p.step} ${p.phase || p.message || ""}`,
      seq: ev.seq,
    });
  }
}

async function pollRun(runId: string) {
  let done = false;
  let lastSeq = 0;
  const seen = new Set<number>();
  while (!done) {
    const data = await api(`/v1/runs/${runId}/events`);
    const events = data.events || [];
    for (const ev of events) {
      if (seen.has(ev.seq)) continue;
      seen.add(ev.seq);
      lastSeq = Math.max(lastSeq, ev.seq);
      pushEventToTimeline(ev);
    }
    const runData = await api(`/v1/runs/${runId}`);
    const st = runData.run?.status;
    runStatus.value = st;
    if (st === "succeeded" || st === "failed" || st === "cancelled") {
      done = true;
      break;
    }
    await new Promise((r) => setTimeout(r, 400));
  }
  if (activeTaskId.value) {
    const t = await api(`/v1/tasks/${activeTaskId.value}`);
    const arts = t.artifacts || [];
    if (arts.length) {
      artifact.value = arts.map((a: { title: string; inline: string }) => `# ${a.title}\n\n${a.inline}`).join("\n\n---\n\n");
    }
  }
  await refreshChanges();
}

async function startTask() {
  await ensureToken();
  busy.value = true;
  messages.value.push({ kind: "user", text: prompt.value });
  try {
    const data = await api("/v1/tasks", {
      method: "POST",
      body: JSON.stringify({ title: prompt.value.slice(0, 40), prompt: prompt.value }),
    });
    activeTaskId.value = data.task.id;
    activeRunId.value = data.run.id;
    runStatus.value = data.run.status;
    await refreshTasks();
    await pollRun(data.run.id);
  } catch (e) {
    messages.value.push({ kind: "system", text: `任务失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function cancelActive() {
  if (!activeRunId.value) return;
  try {
    await api(`/v1/runs/${activeRunId.value}/cancel`, { method: "POST", body: "{}" });
    messages.value.push({ kind: "system", text: "已请求取消 Run" });
  } catch (e) {
    messages.value.push({ kind: "system", text: `取消失败: ${String(e)}` });
  }
}

async function crossSchoolDemo() {
  await ensureToken();
  busy.value = true;
  try {
    const data = await api("/v1/demo/cross-school-deny", { method: "POST", body: "{}" });
    activeTaskId.value = data.task_id;
    activeRunId.value = data.run_id;
    messages.value.push({
      kind: "system",
      text: `跨校演示 run=${data.run_id} denied=${data.denied}`,
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
        summary: "示例提案：不写学校库，仅审计。",
        payload: { action: "reassign_class", class_id: "cls-a1" },
        task_id: activeTaskId.value,
        run_id: activeRunId.value,
      }),
    });
    messages.value.push({
      kind: "system",
      text: `已创建待确认提案 ${data.change.id}`,
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
      text: `已确认提案 ${id} · 审计已记 · 无业务静默写入`,
    });
    artifact.value =
      artifact.value +
      `\n\n## 审计\n\n\`\`\`json\n${JSON.stringify(data.change, null, 2)}\n\`\`\``;
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
  if (arts.length) {
    artifact.value = arts
      .map((a: { title: string; inline: string }) => `# ${a.title}\n\n${a.inline}`)
      .join("\n\n");
  }
}

onMounted(async () => {
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
      <h2>历史 / 任务</h2>
      <p class="muted">school 隔离 · Pico 账本</p>
      <ul class="list">
        <li
          v-for="t in tasks"
          :key="t.id"
          :class="{ active: t.id === activeTaskId }"
          @click="selectTask(t.id)"
        >
          {{ t.title }}
        </li>
        <li v-if="!tasks.length" class="muted">暂无任务</li>
      </ul>

      <div style="margin-top: 1.25rem">
        <h2>测试签发 (S4)</h2>
        <div class="row" style="margin-top: 0.5rem">
          <input v-model="schoolId" placeholder="school_id" />
        </div>
        <div class="row" style="margin-top: 0.4rem">
          <input v-model="membershipId" placeholder="membership_id" />
        </div>
        <div class="row" style="margin-top: 0.5rem">
          <button :disabled="busy" @click="mintToken">签发 token</button>
        </div>
      </div>

      <div style="margin-top: 1.25rem">
        <h2>待确认 (S7)</h2>
        <ul class="list">
          <li v-for="c in changes" :key="c.id">
            <div>{{ c.title }}</div>
            <div class="muted">{{ c.status }}</div>
            <button
              v-if="c.status === 'proposed'"
              style="margin-top: 0.35rem"
              :disabled="busy"
              @click="confirmChange(c.id)"
            >
              确认
            </button>
          </li>
          <li v-if="!changes.length" class="muted">无提案</li>
        </ul>
        <button
          style="margin-top: 0.5rem"
          :disabled="busy"
          @click="proposeChange"
        >
          新建提案
        </button>
      </div>
    </aside>

    <section class="main">
      <header class="main-header">
        <div class="brand">
          Pico
          <span>AI 空间 · Phase 1</span>
        </div>
        <div class="row">
          <span class="pill" :class="safety.includes('OFF') ? 'ok' : 'bad'">{{
            safety
          }}</span>
          <span class="pill">{{ freeze }}</span>
          <span class="pill">run: {{ runStatus }}</span>
          <span class="pill">{{ principalLabel }}</span>
        </div>
      </header>

      <div class="timeline">
        <div
          v-for="(m, i) in messages"
          :key="i"
          class="bubble"
          :class="m.kind"
        >
          {{ m.text }}
        </div>
      </div>

      <div class="composer">
        <textarea v-model="prompt" rows="3" placeholder="描述任务…" />
        <div class="row">
          <button class="primary" :disabled="busy" @click="startTask">
            创建任务并运行
          </button>
          <button :disabled="busy || !activeRunId" @click="cancelActive">
            取消 Run
          </button>
          <button :disabled="busy" @click="crossSchoolDemo">跨校拒绝演示</button>
          <button :disabled="busy" @click="refreshMeta">刷新安全证明</button>
        </div>
        <p class="muted">
          密钥仅服务端 · FakeEdu 合成数据 · 无 edu 联调 · 确认≠写学校库
        </p>
      </div>
    </section>

    <aside class="artifacts">
      <h2>产物</h2>
      <pre class="bubble" style="margin-top: 0.5rem; overflow: auto">{{
        artifact
      }}</pre>
    </aside>
  </div>
</template>
