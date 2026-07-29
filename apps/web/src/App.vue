<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from "vue";
import {
  NButton,
  NCard,
  NConfigProvider,
  NDivider,
  NEmpty,
  NIcon,
  NInput,
  NLayout,
  NLayoutContent,
  NLayoutHeader,
  NLayoutSider,
  NList,
  NListItem,
  NModal,
  NScrollbar,
  NSpace,
  NSpin,
  NTag,
  NText,
  NThing,
  darkTheme,
  type GlobalThemeOverrides,
} from "naive-ui";
import {
  AddOutline,
  ChatbubbleOutline,
  CloseOutline,
  CodeSlashOutline,
  CopyOutline,
  DocumentTextOutline,
  RefreshOutline,
  SendOutline,
  SettingsOutline,
  StopOutline,
} from "@vicons/ionicons5";
import MarkdownIt from "markdown-it";

type Role = "user" | "assistant" | "system" | "tool" | "deny" | "step";
type Msg = {
  id: string;
  role: Role;
  text: string;
  seq?: number;
  toolName?: string;
  ok?: boolean;
};

type TaskItem = { id: string; title: string; created_at?: string };
type ChangeItem = {
  id: string;
  title: string;
  summary: string;
  status: string;
};

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const themeOverrides: GlobalThemeOverrides = {
  common: {
    primaryColor: "#d97757",
    primaryColorHover: "#e08a6d",
    primaryColorPressed: "#c56a4c",
    bodyColor: "#0b0c0f",
    cardColor: "#14161a",
    modalColor: "#14161a",
    popoverColor: "#14161a",
    borderColor: "#2a2e37",
    textColorBase: "#e8eaed",
    textColor1: "#e8eaed",
    textColor2: "#a8b0bd",
    textColor3: "#7a8494",
  },
  Layout: { color: "#0b0c0f", siderColor: "#101218", headerColor: "#0b0c0f" },
  Card: { color: "#14161a", borderColor: "#2a2e37" },
  Input: {
    color: "#16181d",
    colorFocus: "#16181d",
    border: "1px solid #2a2e37",
    borderHover: "1px solid #3d4450",
    borderFocus: "1px solid #d97757",
  },
  Button: { textColorPrimary: "#0b0c0f" },
};

const SUGGESTIONS = [
  { label: "列出我学校的班级", prompt: "列出我学校的班级，并一句话总结。" },
  { label: "工具冒烟 echo", prompt: "请调用 echo 工具输出：pico-proto-ok" },
  { label: "跨校拒绝演示", prompt: "__CROSS_SCHOOL__" },
  { label: "创建待确认提案", prompt: "__PROPOSE__" },
];

const token = ref(localStorage.getItem("pico_token") || "");
const schoolId = ref(localStorage.getItem("pico_school") || "school-a");
const membershipId = ref(localStorage.getItem("pico_member") || "member-1");
const prompt = ref("");
const messages = ref<Msg[]>([]);
const tasks = ref<TaskItem[]>([]);
const changes = ref<ChangeItem[]>([]);
const activeTaskId = ref<string | null>(null);
const activeRunId = ref<string | null>(null);
const runStatus = ref("idle");
const busy = ref(false);
const safetyOk = ref(false);
const freezeLabel = ref("…");
const modelReady = ref(true);
const showSteps = ref(false);
const artifactOpen = ref(true);
const artifactTitle = ref("Artifact");
const artifactBody = ref("");
const siderCollapsed = ref(false);
const settingsOpen = ref(false);
const errorText = ref("");
const abortPoll = ref(false); // legacy name: stop stream/poll
let streamAbort: AbortController | null = null;
const stopHint = ref("");

const pendingApprovals = computed(() =>
  changes.value.filter((c) => c.status === "proposed"),
);
const canStop = computed(
  () =>
    (busy.value && runStatus.value !== "succeeded" && runStatus.value !== "failed") ||
    runStatus.value === "running" ||
    runStatus.value === "queued",
);
const isEmpty = computed(() => messages.value.length === 0);

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function renderMd(text: string) {
  return md.render(text || "");
}

function authHeaders(): Headers {
  const h = new Headers({ "Content-Type": "application/json" });
  if (token.value) h.set("Authorization", `Bearer ${token.value}`);
  return h;
}

function friendlyError(err: unknown): string {
  if (err instanceof Error) {
    const m = err.message || "";
    if (/密钥|模型服务|超时|限流|跨校|登录|找不到|未能完成|出了点问题|处理超时|无法连接/.test(m)) {
      return m;
    }
    if (/blocked s1|kimi_api_key|api key/i.test(m)) {
      return "模型服务未配置或密钥无效。请管理员配置 API 密钥后重试。";
    }
    if (/failed to fetch|networkerror|load failed/i.test(m)) {
      return "无法连接 Pico 服务，请确认 API 已启动。";
    }
    return m.replace(/^Error:\s*/i, "") || "请求失败，请重试。";
  }
  return String(err ?? "请求失败");
}

async function api(path: string, init: RequestInit = {}) {
  const headers = authHeaders();
  if (init.headers) {
    new Headers(init.headers).forEach((v, k) => headers.set(k, v));
  }
  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch (e) {
    throw new Error(friendlyError(e));
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const d = data?.detail;
    const msg =
      typeof d === "string"
        ? d
        : d?.message || d?.code || res.statusText || "request failed";
    throw new Error(friendlyError(new Error(String(msg))));
  }
  return data;
}

async function scrollBottom() {
  await nextTick();
  // NScrollbar exposes scrollTo via ref in some versions — fallback DOM
  const el = document.querySelector(".chat-scroll .n-scrollbar-container");
  if (el) el.scrollTop = el.scrollHeight;
}

watch(messages, () => void scrollBottom(), { deep: true });

async function refreshMeta() {
  try {
    const s = await api("/v1/meta/agent-safety");
    safetyOk.value = !!s.proof?.dangerous_off;
  } catch {
    safetyOk.value = false;
  }
  try {
    const f = await api("/v1/meta/freeze");
    const pins = f.agent_pins || {};
    modelReady.value = f.model_ready !== false;
    if (f.model_ready === false) {
      freezeLabel.value = "模型未配置密钥";
    } else {
      const prov = f.model_provider || "model";
      const name = f.model_name || pins["kimi-agent-sdk"] || "?";
      freezeLabel.value = `${prov} · ${name}`;
    }
  } catch {
    freezeLabel.value = "无法读取模型状态";
    modelReady.value = false;
  }
}

async function mintToken() {
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

function pushMsg(partial: Omit<Msg, "id"> & { id?: string }) {
  messages.value.push({ id: partial.id || uid(), ...partial });
}

function applyEvent(ev: {
  seq: number;
  type: string;
  payload: Record<string, unknown>;
}) {
  const p = ev.payload || {};
  if (ev.type === "message.delta" || ev.type === "message.final") {
    const text = String(p.text || "");
    if (!text) return;
    const last = messages.value[messages.value.length - 1];
    if (last?.role === "assistant" && ev.type === "message.delta") {
      // Multi-step emits per-step chunks — append rather than clobber.
      last.text = last.text ? `${last.text}${text}` : text;
      last.seq = ev.seq;
    } else if (last?.role === "assistant" && ev.type === "message.final") {
      last.text = text;
      last.seq = ev.seq;
    } else {
      pushMsg({ role: "assistant", text, seq: ev.seq });
    }
  } else if (ev.type === "tool.call") {
    pushMsg({
      role: "tool",
      text: JSON.stringify(p.arguments || {}, null, 2),
      toolName: String(p.tool || "tool"),
      seq: ev.seq,
    });
  } else if (ev.type === "tool.result") {
    pushMsg({
      role: "tool",
      text: p.ok
        ? JSON.stringify(p.result, null, 2)
        : String(p.message || p.code || "工具失败"),
      toolName: String(p.tool || "tool"),
      ok: !!p.ok,
      seq: ev.seq,
    });
  } else if (ev.type === "auth.deny") {
    pushMsg({
      role: "deny",
      text: String(p.message || p.code || "访问被拒绝"),
      seq: ev.seq,
    });
  } else if (ev.type === "agent.step") {
    if (showSteps.value) {
      pushMsg({
        role: "step",
        text: `步骤 ${p.step}${p.phase ? ` · ${p.phase}` : ""}${p.message ? ` — ${p.message}` : ""}`,
        seq: ev.seq,
      });
    }
  } else if (ev.type === "run.error") {
    const um = String(p.user_message || "");
    if (um) {
      errorText.value = um;
    }
  } else if (ev.type === "run.status") {
    runStatus.value = String(p.status || "");
    if (p.status === "failed") {
      const um = String(p.user_message || friendlyError(p.reason) || "运行失败");
      errorText.value = um;
      // Avoid double error rows when message.final already carries the same text.
      const already = messages.value.some(
        (m) =>
          (m.role === "assistant" || m.role === "system") &&
          (m.text === um || m.text.includes(um) || um.includes(m.text)),
      );
      if (!already) {
        pushMsg({ role: "assistant", text: um, seq: ev.seq });
      }
    }
  } else if (ev.type === "artifact.created") {
    artifactTitle.value = String(p.title || "Artifact");
    artifactOpen.value = true;
  }
}

async function loadArtifacts(taskId: string) {
  const t = await api(`/v1/tasks/${taskId}`);
  const arts = t.artifacts || [];
  if (arts.length) {
    artifactTitle.value = arts[0].title || "Artifact";
    artifactBody.value = arts
      .map((a: { title: string; inline: string }) => `# ${a.title}\n\n${a.inline}`)
      .join("\n\n---\n\n");
    artifactOpen.value = true;
  }
}

function parseSseChunk(
  buffer: string,
): { events: { event: string; data: string }[]; rest: string } {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  const events: { event: string; data: string }[] = [];
  for (const block of parts) {
    if (!block.trim()) continue;
    let evName = "message";
    const dataLines: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) evName = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
      else if (line.startsWith("data: ")) dataLines.push(line.slice(6));
    }
    events.push({ event: evName, data: dataLines.join("\n") });
  }
  return { events, rest };
}

/** True SSE via fetch (Bearer auth; EventSource cannot set Authorization). */
async function streamRun(runId: string) {
  const seen = new Set<number>();
  abortPoll.value = false;
  stopHint.value = "";
  streamAbort = new AbortController();
  try {
    const res = await fetch(`/v1/runs/${runId}/stream`, {
      method: "GET",
      headers: {
        Accept: "text/event-stream",
        ...(token.value ? { Authorization: `Bearer ${token.value}` } : {}),
      },
      signal: streamAbort.signal,
    });
    if (!res.ok) {
      const body = await res.text().catch(() => "");
      throw new Error(body || `流式连接失败 (${res.status})`);
    }
    if (!res.body) {
      // Fallback environments without stream body
      await pollRunFallback(runId, seen);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    while (!abortPoll.value) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });
      const parsed = parseSseChunk(buf);
      buf = parsed.rest;
      for (const raw of parsed.events) {
        if (raw.event === "stream.end") {
          try {
            const d = JSON.parse(raw.data || "{}") as { status?: string };
            if (d.status) runStatus.value = d.status;
          } catch {
            /* ignore */
          }
          continue;
        }
        try {
          const ev = JSON.parse(raw.data || "{}") as {
            seq: number;
            type: string;
            payload: Record<string, unknown>;
          };
          if (ev.seq != null) {
            if (seen.has(ev.seq)) continue;
            seen.add(ev.seq);
          }
          // Prefer payload type from ledger event
          applyEvent({
            seq: ev.seq,
            type: ev.type || raw.event,
            payload: ev.payload || {},
          });
        } catch {
          /* ignore malformed */
        }
      }
      if (["succeeded", "failed", "cancelled"].includes(runStatus.value)) break;
    }
    // Drain any final status if stream closed without stream.end
    if (!["succeeded", "failed", "cancelled"].includes(runStatus.value)) {
      try {
        const runData = await api(`/v1/runs/${runId}`);
        runStatus.value = runData.run?.status || runStatus.value;
      } catch {
        /* ignore */
      }
    }
    if (activeTaskId.value) await loadArtifacts(activeTaskId.value);
    await refreshChanges();
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") {
      stopHint.value = "已停止";
      runStatus.value = runStatus.value === "running" ? "cancelled" : runStatus.value;
      return;
    }
    const msg = friendlyError(e);
    errorText.value = msg;
    // Fallback to poll if SSE path fails (proxy/version)
    try {
      await pollRunFallback(runId, seen);
    } catch {
      pushMsg({ role: "assistant", text: msg });
      runStatus.value = "failed";
    }
  } finally {
    streamAbort = null;
  }
}

async function pollRunFallback(runId: string, seen: Set<number>) {
  while (!abortPoll.value) {
    const data = await api(`/v1/runs/${runId}/events`);
    for (const ev of data.events || []) {
      if (seen.has(ev.seq)) continue;
      seen.add(ev.seq);
      applyEvent(ev);
    }
    const runData = await api(`/v1/runs/${runId}`);
    runStatus.value = runData.run?.status || runStatus.value;
    if (runData.run?.error && runStatus.value === "failed" && !errorText.value) {
      errorText.value = friendlyError(runData.run.error);
    }
    if (["succeeded", "failed", "cancelled"].includes(runStatus.value)) break;
    await new Promise((r) => setTimeout(r, 300));
  }
  if (activeTaskId.value) await loadArtifacts(activeTaskId.value);
  await refreshChanges();
}

async function newChat() {
  messages.value = [];
  activeTaskId.value = null;
  activeRunId.value = null;
  runStatus.value = "idle";
  artifactBody.value = "";
  prompt.value = "";
  errorText.value = "";
}

async function sendPrompt(raw?: string) {
  const text = (raw ?? prompt.value).trim();
  if (!text || busy.value) return;

  if (text === "__CROSS_SCHOOL__") {
    prompt.value = "";
    await runCrossSchool();
    return;
  }
  if (text === "__PROPOSE__") {
    prompt.value = "";
    await proposeChange();
    return;
  }

  await ensureToken();
  busy.value = true;
  errorText.value = "";
  prompt.value = "";
  pushMsg({ role: "user", text });
  try {
    const data = await api("/v1/tasks", {
      method: "POST",
      body: JSON.stringify({ title: text.slice(0, 48), prompt: text }),
    });
    activeTaskId.value = data.task.id;
    activeRunId.value = data.run.id;
    runStatus.value = data.run.status;
    await refreshTasks();
    await streamRun(data.run.id);
  } catch (e) {
    const msg = friendlyError(e);
    errorText.value = msg;
    pushMsg({ role: "assistant", text: msg });
  } finally {
    busy.value = false;
  }
}

async function stopRun() {
  abortPoll.value = true;
  stopHint.value = "正在停止…";
  // Cut SSE immediately so UI unblocks
  try {
    streamAbort?.abort();
  } catch {
    /* ignore */
  }
  streamAbort = null;
  if (!activeRunId.value) {
    busy.value = false;
    runStatus.value = "cancelled";
    stopHint.value = "已停止";
    return;
  }
  try {
    await api(`/v1/runs/${activeRunId.value}/cancel`, {
      method: "POST",
      body: "{}",
    });
    runStatus.value = "cancelled";
    stopHint.value = "已停止";
    const last = messages.value[messages.value.length - 1];
    if (!(last?.role === "system" && last.text.includes("停止"))) {
      pushMsg({ role: "system", text: "已停止生成" });
    }
  } catch (e) {
    errorText.value = friendlyError(e);
    stopHint.value = "";
  } finally {
    busy.value = false;
  }
}

async function runCrossSchool() {
  await ensureToken();
  busy.value = true;
  try {
    const data = await api("/v1/demo/cross-school-deny", {
      method: "POST",
      body: "{}",
    });
    activeTaskId.value = data.task_id;
    activeRunId.value = data.run_id;
    pushMsg({ role: "system", text: "跨校访问演示（网关 fail-closed）" });
    for (const ev of data.events || []) applyEvent(ev);
    await refreshTasks();
  } catch (e) {
    pushMsg({ role: "assistant", text: friendlyError(e) });
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
        title: "调整一年级分班",
        summary: "Codex/Claude 式待确认：人工批准后才可进入回写。",
        payload: { action: "reassign_class", class_id: "cls-a1" },
        task_id: activeTaskId.value,
        run_id: activeRunId.value,
      }),
    });
    pushMsg({
      role: "system",
      text: `待确认提案已创建 · ${data.change.id.slice(0, 8)}…`,
    });
    await refreshChanges();
  } catch (e) {
    pushMsg({ role: "assistant", text: friendlyError(e) });
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
    pushMsg({
      role: "system",
      text: "已批准变更 · 审计已记 · 未静默写业务库",
    });
    artifactBody.value =
      (artifactBody.value || "") +
      `\n\n## Approval audit\n\n\`\`\`json\n${JSON.stringify(data.change, null, 2)}\n\`\`\``;
    artifactOpen.value = true;
    await refreshChanges();
  } catch (e) {
    errorText.value = friendlyError(e);
  } finally {
    busy.value = false;
  }
}

async function openTask(id: string) {
  await ensureToken();
  activeTaskId.value = id;
  messages.value = [];
  errorText.value = "";
  const t = await api(`/v1/tasks/${id}`);
  // load latest run — restore user prompt as first bubble (not only system+events)
  const runs = await api(`/v1/tasks/${id}/runs`);
  const run = (runs.runs || [])[0];
  if (run) {
    activeRunId.value = run.id;
    runStatus.value = run.status;
    const userText = String(run.prompt || t.task?.title || "").trim();
    if (userText) {
      pushMsg({ role: "user", text: userText });
    } else {
      pushMsg({ role: "system", text: `会话：${t.task?.title || id}` });
    }
    const evs = await api(`/v1/runs/${run.id}/events`);
    for (const ev of evs.events || []) applyEvent(ev);
  } else {
    pushMsg({ role: "system", text: `会话：${t.task?.title || id}` });
  }
  await loadArtifacts(id);
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    /* ignore */
  }
}

function onKeydown(e: KeyboardEvent) {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
    e.preventDefault();
    void sendPrompt();
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
  try {
    await refreshMeta();
    await ensureToken();
    await refreshTasks();
    await refreshChanges();
  } catch (e) {
    errorText.value = friendlyError(e);
  }
});
</script>

<template>
  <n-config-provider :theme="darkTheme" :theme-overrides="themeOverrides">
    <n-layout has-sider style="height: 100vh">
      <!-- ===== Left: conversations (Claude/Codex style) ===== -->
      <n-layout-sider
        bordered
        collapse-mode="width"
        :collapsed-width="64"
        :width="280"
        :collapsed="siderCollapsed"
        show-trigger
        @collapse="siderCollapsed = true"
        @expand="siderCollapsed = false"
        :native-scrollbar="false"
        style="border-right: 1px solid #2a2e37"
      >
        <div style="padding: 12px; display: flex; flex-direction: column; height: 100%; gap: 10px">
          <n-button type="primary" block strong :disabled="busy" @click="newChat">
            <template #icon>
              <n-icon :component="AddOutline" />
            </template>
            {{ siderCollapsed ? "" : "新对话" }}
          </n-button>

          <div v-if="!siderCollapsed" style="flex: 1; min-height: 0; display: flex; flex-direction: column">
            <n-text depth="3" style="font-size: 12px; margin: 4px 0">会话</n-text>
            <n-scrollbar style="flex: 1">
              <n-list hoverable clickable style="background: transparent">
                <n-list-item
                  v-for="t in tasks"
                  :key="t.id"
                  @click="openTask(t.id)"
                  :style="{
                    background: t.id === activeTaskId ? '#1a1d24' : 'transparent',
                    borderRadius: '8px',
                    marginBottom: '4px',
                    cursor: 'pointer',
                  }"
                >
                  <n-thing>
                    <template #avatar>
                      <n-icon :component="ChatbubbleOutline" depth="3" />
                    </template>
                    <template #header>
                      <span style="font-size: 13px; line-height: 1.3">{{ t.title }}</span>
                    </template>
                  </n-thing>
                </n-list-item>
                <n-empty v-if="!tasks.length" description="尚无会话" size="small" style="margin-top: 24px" />
              </n-list>
            </n-scrollbar>

            <n-divider style="margin: 10px 0" />
            <n-text depth="3" style="font-size: 12px">待确认 · Approvals</n-text>
            <n-scrollbar style="max-height: 160px; margin-top: 6px">
              <div v-for="c in pendingApprovals" :key="c.id" style="margin-bottom: 8px">
                <n-card size="small" :bordered="true">
                  <div style="font-size: 12px; margin-bottom: 6px">{{ c.title }}</div>
                  <n-button size="tiny" type="primary" :disabled="busy" @click="confirmChange(c.id)">
                    批准
                  </n-button>
                </n-card>
              </div>
              <n-text v-if="!pendingApprovals.length" depth="3" style="font-size: 12px">无待办</n-text>
            </n-scrollbar>

            <n-divider style="margin: 10px 0" />
            <n-space vertical :size="6">
              <n-tag size="small" :type="safetyOk ? 'success' : 'error'" round>
                {{ safetyOk ? "Tools sandbox OFF" : "Safety ?" }}
              </n-tag>
              <n-text depth="3" style="font-size: 11px">{{ freezeLabel }}</n-text>
              <n-button size="tiny" quaternary @click="showSteps = !showSteps">
                {{ showSteps ? "隐藏步骤" : "显示步骤" }}
              </n-button>
              <n-button size="tiny" quaternary @click="settingsOpen = true">
                <template #icon><n-icon :component="SettingsOutline" /></template>
                身份 / 设置
              </n-button>
            </n-space>
          </div>
        </div>
      </n-layout-sider>

      <!-- ===== Center: chat ===== -->
      <n-layout>
        <n-layout-header
          bordered
          style="height: 52px; display: flex; align-items: center; justify-content: space-between; padding: 0 16px"
        >
          <n-space align="center">
            <n-text strong style="font-size: 15px">Pico</n-text>
            <n-tag size="small" round :bordered="false" type="warning">Claude / Codex 式工作台</n-tag>
            <n-tag size="small" round :type="runStatus === 'running' ? 'info' : 'default'">
              {{ runStatus }}
            </n-tag>
          </n-space>
          <n-space>
            <n-button size="small" quaternary @click="artifactOpen = !artifactOpen">
              <template #icon><n-icon :component="DocumentTextOutline" /></template>
              Artifacts
            </n-button>
            <n-button size="small" quaternary :disabled="busy" @click="refreshMeta">
              <template #icon><n-icon :component="RefreshOutline" /></template>
            </n-button>
          </n-space>
        </n-layout-header>

        <n-layout has-sider position="absolute" style="top: 52px; bottom: 0">
          <n-layout-content content-style="display:flex;flex-direction:column;height:100%">
            <div
              v-if="!modelReady"
              style="padding: 8px 16px; background: #3a321f; color: #ffd59a; font-size: 13px; display: flex; justify-content: space-between; gap: 12px"
            >
              <span>模型 API 密钥未配置：对话将无法调用大模型。请在服务端设置 KIMI_API_KEY 或 DEEPSEEK_API_KEY。</span>
              <n-button size="tiny" quaternary @click="refreshMeta">刷新状态</n-button>
            </div>
            <div
              v-if="errorText"
              style="padding: 8px 16px; background: #3a1f1f; color: #ffb4b4; font-size: 13px; display: flex; justify-content: space-between; align-items: center; gap: 12px"
            >
              <span>{{ errorText }}</span>
              <n-button size="tiny" quaternary style="color: #ffb4b4" @click="errorText = ''">关闭</n-button>
            </div>

            <!-- messages -->
            <n-scrollbar class="chat-scroll" style="flex: 1; padding: 0 0 12px">
              <div style="max-width: 820px; margin: 0 auto; padding: 20px 20px 40px">
                <!-- empty / home -->
                <div v-if="isEmpty" style="text-align: center; padding: 64px 12px 32px">
                  <n-text style="font-size: 28px; font-weight: 600">今天要交办什么？</n-text>
                  <p style="color: #7a8494; margin: 12px 0 28px; font-size: 14px">
                    对话 · 工具调用 · 产物 · 人工确认。失败会用中文说明原因，而不是堆栈。
                  </p>
                  <n-space justify="center" wrap>
                    <n-button
                      v-for="s in SUGGESTIONS"
                      :key="s.label"
                      secondary
                      round
                      :disabled="busy"
                      @click="sendPrompt(s.prompt)"
                    >
                      {{ s.label }}
                    </n-button>
                  </n-space>
                </div>

                <div v-for="m in messages" :key="m.id" style="margin-bottom: 18px">
                  <!-- user -->
                  <div v-if="m.role === 'user'" style="display: flex; justify-content: flex-end">
                    <div
                      style="
                        max-width: 85%;
                        background: #2a231f;
                        border: 1px solid #4a3a32;
                        border-radius: 16px 16px 4px 16px;
                        padding: 10px 14px;
                        font-size: 14.5px;
                        white-space: pre-wrap;
                      "
                    >
                      {{ m.text }}
                    </div>
                  </div>

                  <!-- assistant -->
                  <div v-else-if="m.role === 'assistant'" style="display: flex; gap: 10px">
                    <div
                      style="
                        width: 28px;
                        height: 28px;
                        border-radius: 8px;
                        background: linear-gradient(135deg, #d97757, #c45c3e);
                        flex-shrink: 0;
                      "
                    />
                    <div style="flex: 1; min-width: 0">
                      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px">
                        <n-text strong style="font-size: 13px">Pico</n-text>
                        <n-button text size="tiny" @click="copyText(m.text)">
                          <template #icon><n-icon :component="CopyOutline" :size="14" /></template>
                        </n-button>
                      </div>
                      <div class="msg-md" v-html="renderMd(m.text)" />
                    </div>
                  </div>

                  <!-- tool use card (Codex/Claude tool blocks) -->
                  <div v-else-if="m.role === 'tool'" style="margin-left: 38px">
                    <n-card size="small" embedded style="background: #12141a; border: 1px solid #2a2e37">
                      <template #header>
                        <n-space align="center" :size="8">
                          <n-icon :component="CodeSlashOutline" />
                          <n-text strong style="font-size: 12px">Tool · {{ m.toolName }}</n-text>
                          <n-tag
                            v-if="m.ok !== undefined"
                            size="tiny"
                            :type="m.ok ? 'success' : 'error'"
                            round
                          >
                            {{ m.ok ? "ok" : "fail" }}
                          </n-tag>
                        </n-space>
                      </template>
                      <pre style="margin: 0; font-size: 12px; white-space: pre-wrap; color: #a8b0bd">{{ m.text }}</pre>
                    </n-card>
                  </div>

                  <!-- deny -->
                  <div v-else-if="m.role === 'deny'" style="margin-left: 38px">
                    <n-card size="small" style="border-color: #5a3030; background: #1f1414">
                      <n-text type="error" style="font-size: 13px">拒绝 · {{ m.text }}</n-text>
                    </n-card>
                  </div>

                  <!-- step / system -->
                  <div v-else style="margin-left: 38px">
                    <n-text depth="3" style="font-size: 12px">{{ m.text }}</n-text>
                  </div>
                </div>

                <div v-if="busy || stopHint" style="margin-left: 38px; display: flex; align-items: center; gap: 8px">
                  <n-spin v-if="busy && !stopHint" size="small" />
                  <n-text depth="3" style="font-size: 13px">{{ stopHint || "Agent 运行中（SSE）…" }}</n-text>
                </div>
              </div>
            </n-scrollbar>

            <!-- composer -->
            <div style="border-top: 1px solid #2a2e37; padding: 12px 16px 16px; background: #0b0c0f">
              <div style="max-width: 820px; margin: 0 auto">
                <div
                  style="
                    border: 1px solid #2a2e37;
                    border-radius: 16px;
                    background: #14161a;
                    padding: 10px 12px;
                  "
                >
                  <n-input
                    v-model:value="prompt"
                    type="textarea"
                    :autosize="{ minRows: 1, maxRows: 8 }"
                    placeholder="给 Pico 下指令…（⌘/Ctrl+Enter 发送）"
                    :bordered="false"
                    @keydown="onKeydown"
                  />
                  <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 8px">
                    <n-space :size="6">
                      <n-tag size="tiny" round :bordered="false">多步工具</n-tag>
                      <n-tag size="tiny" round :bordered="false">Artifacts</n-tag>
                      <n-tag size="tiny" round :bordered="false">人工批准</n-tag>
                    </n-space>
                    <n-space>
                      <n-button
                        v-if="canStop"
                        type="warning"
                        secondary
                        round
                        @click="stopRun"
                      >
                        <template #icon><n-icon :component="StopOutline" /></template>
                        停止
                      </n-button>
                      <n-button
                        type="primary"
                        round
                        strong
                        :disabled="busy || !prompt.trim()"
                        :loading="busy"
                        @click="sendPrompt()"
                      >
                        <template #icon><n-icon :component="SendOutline" /></template>
                        发送
                      </n-button>
                    </n-space>
                  </div>
                </div>
                <n-text depth="3" style="display: block; text-align: center; font-size: 11px; margin-top: 8px">
                  Pico 独立原型 · 密钥仅服务端 · 确认≠写学校库
                </n-text>
              </div>
            </div>
          </n-layout-content>

          <!-- ===== Right: Artifacts (Claude style) ===== -->
          <n-layout-sider
            v-if="artifactOpen"
            bordered
            :width="400"
            :native-scrollbar="false"
            style="border-left: 1px solid #2a2e37"
          >
            <div style="display: flex; flex-direction: column; height: 100%">
              <div
                style="
                  height: 48px;
                  display: flex;
                  align-items: center;
                  justify-content: space-between;
                  padding: 0 12px;
                  border-bottom: 1px solid #2a2e37;
                "
              >
                <n-space align="center" :size="8">
                  <n-icon :component="DocumentTextOutline" />
                  <n-text strong style="font-size: 13px">{{ artifactTitle }}</n-text>
                </n-space>
                <n-button text @click="artifactOpen = false">
                  <template #icon><n-icon :component="CloseOutline" /></template>
                </n-button>
              </div>
              <n-scrollbar style="flex: 1; padding: 16px">
                <div v-if="artifactBody" class="msg-md" v-html="renderMd(artifactBody)" />
                <n-empty v-else description="工具产物会显示在这里（表、文档、审计）" style="margin-top: 48px" />
              </n-scrollbar>
            </div>
          </n-layout-sider>
        </n-layout>
      </n-layout>
    </n-layout>

    <!-- settings modal -->
    <n-modal v-model:show="settingsOpen" preset="card" title="身份与设置" style="width: 420px">
      <n-space vertical>
        <n-text depth="3" style="font-size: 12px">school_id</n-text>
        <n-input v-model:value="schoolId" />
        <n-text depth="3" style="font-size: 12px">membership_id</n-text>
        <n-input v-model:value="membershipId" />
        <n-button type="primary" block :disabled="busy" @click="mintToken().then(() => (settingsOpen = false))">
          重新签发测试凭证
        </n-button>
        <n-text depth="3" style="font-size: 12px">
          原型使用测试签发器；claim 形状预留对接。不连 edu。
        </n-text>
      </n-space>
    </n-modal>
  </n-config-provider>
</template>
