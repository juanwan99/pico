/**
 * Browser → LibreChat `/api/pico` → Pico ledger (Task/Run/Artifact/Workspace).
 */

export type PicoArtifact = {
  id: string;
  kind: string;
  title: string;
  inline?: string;
  run_id?: string | null;
};

export type PicoTask = {
  id: string;
  title: string;
  conversation_id?: string | null;
  workspace_id?: string | null;
  created_at?: string | null;
};

export type PicoRun = {
  id: string;
  task_id: string;
  status: string;
  model?: string;
  error?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  token_usage?: Record<string, unknown>;
};

export type PicoWorkspace = {
  id: string;
  name: string;
  kind: string;
  note?: string;
  created_at?: string | null;
};

async function picoFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/pico${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`pico ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export async function listPicoTasks(conversationId?: string) {
  const q = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : '';
  return picoFetch<{ tasks: PicoTask[] }>(`/v1/tasks${q}`);
}

export async function getPicoTask(taskId: string) {
  return picoFetch<{ task: PicoTask; artifacts: PicoArtifact[] }>(`/v1/tasks/${taskId}`);
}

export async function listPicoTaskRuns(taskId: string) {
  return picoFetch<{ runs: PicoRun[] }>(`/v1/tasks/${taskId}/runs`);
}

export async function listPicoWorkspaces() {
  return picoFetch<{ workspaces: PicoWorkspace[] }>(`/v1/workspaces`);
}

export async function createPicoWorkspace(name: string, note = '') {
  return picoFetch<{ workspace: PicoWorkspace }>(`/v1/workspaces`, {
    method: 'POST',
    body: JSON.stringify({ name, note, kind: 'managed' }),
  });
}

export async function deletePicoWorkspace(id: string) {
  return picoFetch<{ ok: boolean }>(`/v1/workspaces/${id}`, { method: 'DELETE' });
}


export async function rebindConversation(fromId: string, toId: string) {
  return picoFetch<{ updated: number; from: string; to: string }>(`/v1/tasks/rebind-conversation`, {
    method: 'POST',
    body: JSON.stringify({ from_conversation_id: fromId, to_conversation_id: toId }),
  });
}

export type PicoAutomation = {
  id: string;
  name: string;
  prompt: string;
  schedule_kind: string;
  schedule: Record<string, unknown>;
  enabled: boolean;
  last_run_at?: string | null;
  next_run_at?: string | null;
};

export async function listPicoAutomations() {
  return picoFetch<{ automations: PicoAutomation[] }>(`/v1/automations`);
}

export async function createPicoAutomation(body: {
  name: string;
  prompt: string;
  schedule_kind: string;
  schedule: Record<string, unknown>;
}) {
  return picoFetch<{ automation: PicoAutomation }>(`/v1/automations`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

export async function setPicoAutomationEnabled(id: string, enabled: boolean) {
  const path = enabled ? `/v1/automations/${id}/enable` : `/v1/automations/${id}/disable`;
  return picoFetch<{ automation: PicoAutomation }>(path, { method: 'POST' });
}

export async function deletePicoAutomation(id: string) {
  return picoFetch<{ ok: boolean }>(`/v1/automations/${id}`, { method: 'DELETE' });
}
