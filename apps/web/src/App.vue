<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type Msg =
  | { kind: "system"; text: string }
  | { kind: "user"; text: string }
  | { kind: "assistant"; text: string }
  | { kind: "tool"; text: string };

const apiBase = ref("");
const token = ref("");
const schoolId = ref("school-a");
const membershipId = ref("member-1");
const prompt = ref("列出我学校的班级（将走 FakeEdu 工具）");
const messages = ref<Msg[]>([
  {
    kind: "system",
    text: "Pico D1 scaffold — Claude 式三区壳。D2 接通真实 Run/Event 流。",
  },
]);
const safety = ref<string>("…");
const freeze = ref<string>("…");
const artifact = ref(
  "产物区（D1 占位）\n\nD2 起：展示 Run 产物文档/表格。\n当前可查看鉴权 claims 与工具结果。",
);
const busy = ref(false);
const principalLabel = computed(() =>
  token.value ? `${schoolId.value} / ${membershipId.value}` : "未签发",
);

async function api(path: string, init: RequestInit = {}) {
  const headers = new Headers(init.headers || {});
  if (token.value) headers.set("Authorization", `Bearer ${token.value}`);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`${apiBase.value}${path}`, { ...init, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail?.message || data?.detail || res.statusText);
  }
  return data;
}

async function refreshMeta() {
  try {
    const s = await api("/v1/meta/agent-safety");
    safety.value = s.proof?.dangerous_off
      ? "Shell/File/Web/MCP OFF"
      : "SAFETY FAIL";
  } catch (e) {
    safety.value = `API offline (${String(e)})`;
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
    messages.value.push({
      kind: "system",
      text: `已签发测试凭证 school_id=${schoolId.value}（S4 形状）。`,
    });
    artifact.value = JSON.stringify(data.claims_shape, null, 2);
  } catch (e) {
    messages.value.push({ kind: "system", text: `签发失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function callFakeEdu() {
  if (!token.value) {
    await mintToken();
  }
  busy.value = true;
  messages.value.push({ kind: "user", text: prompt.value });
  try {
    const data = await api("/v1/tools/invoke", {
      method: "POST",
      body: JSON.stringify({
        name: "fake_edu.list_classes",
        arguments: {},
      }),
    });
    messages.value.push({
      kind: "tool",
      text: `tool fake_edu.list_classes →\n${JSON.stringify(data.result, null, 2)}`,
    });
    artifact.value = `# Classes\n\n\`\`\`json\n${JSON.stringify(data.result, null, 2)}\n\`\`\``;
  } catch (e) {
    messages.value.push({ kind: "system", text: `工具失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

async function modelHello() {
  if (!token.value) await mintToken();
  busy.value = true;
  messages.value.push({ kind: "user", text: "model hello (S1)" });
  try {
    const data = await api("/v1/dev/model-hello", {
      method: "POST",
      body: JSON.stringify({ prompt: "Reply with: pico-hello-ok" }),
    });
    if (data.status === "BLOCKED") {
      messages.value.push({
        kind: "system",
        text: `S1 BLOCKED: ${data.reason}`,
      });
    } else {
      messages.value.push({
        kind: "assistant",
        text: `[${data.provider}/${data.model}] ${data.text}`,
      });
    }
  } catch (e) {
    messages.value.push({ kind: "system", text: `hello 失败: ${String(e)}` });
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  refreshMeta();
});
</script>

<template>
  <div class="shell">
    <aside class="rail">
      <h2>历史 / 任务</h2>
      <p class="muted">D1 壳 · D2 接 Task 列表</p>
      <ul class="list">
        <li class="active">Demo · FakeEdu 班级</li>
        <li>Demo · 模型 hello</li>
      </ul>
      <div style="margin-top: 1.25rem">
        <h2>测试签发</h2>
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
    </aside>

    <section class="main">
      <header class="main-header">
        <div class="brand">
          Pico
          <span>AI 空间 · Phase 1</span>
        </div>
        <div class="row">
          <span
            class="pill"
            :class="safety.includes('OFF') ? 'ok' : 'bad'"
            >{{ safety }}</span
          >
          <span class="pill">{{ freeze }}</span>
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
        <textarea v-model="prompt" rows="3" placeholder="输入消息…" />
        <div class="row">
          <button class="primary" :disabled="busy" @click="callFakeEdu">
            运行 FakeEdu 工具
          </button>
          <button :disabled="busy" @click="modelHello">模型 hello (S1)</button>
          <button :disabled="busy" @click="refreshMeta">刷新安全证明</button>
        </div>
        <p class="muted">
          密钥仅服务端；无 KIMI_API_KEY 时 S1 诚实 BLOCKED，不用 mock 充数。
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
