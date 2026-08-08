/**
 * Browser → LibreChat `/api/pico` → Pico ledger (Task/Run/Artifact/Workspace).
 * Must send LibreChat JWT (same as other API clients).
 */
import { getTokenHeader } from 'librechat-data-provider';

export type PicoArtifact = {
  id: string;
  kind: string;
  title: string;
  /** Human-facing label (filename); never prefer UUID in UI. */
  user_label?: string;
  /** UTF-8 text only; binary artifacts omit this and must be fetched via content API. */
  inline?: string | null;
  run_id?: string | null;
  content_encoding?: 'utf8' | 'base64' | string;
  byte_size?: number;
  content_sha256?: string;
  /** Relative download path on Pico API (proxied via /api/pico). */
  download_path?: string;
};

export type PicoTaskLatestRun = {
  id: string;
  status: string;
  cancel_requested?: boolean;
  model?: string | null;
  error?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
};

export type PicoTask = {
  id: string;
  title: string;
  conversation_id?: string | null;
  workspace_id?: string | null;
  created_at?: string | null;
  latest_run?: PicoTaskLatestRun | null;
};

/** Teacher-facing one-line status for task lists. */
export function labelForLatestRun(run?: PicoTaskLatestRun | null): string | null {
  if (!run) {
    return null;
  }
  if (run.cancel_requested && ['queued', 'preparing', 'running'].includes(run.status)) {
    return '停止中';
  }
  switch (run.status) {
    case 'queued':
    case 'preparing':
    case 'running':
      return '仍在处理…';
    case 'succeeded':
      return '已完成';
    case 'failed':
      return '失败';
    case 'cancelled':
      return '已停止';
    default:
      return run.status;
  }
}

export type PicoRun = {
  id: string;
  task_id: string;
  status: string;
  cancel_requested?: boolean;
  model?: string;
  error?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  token_usage?: Record<string, unknown>;
};

export type PicoRunEvent = {
  id: string;
  run_id: string;
  seq: number;
  type: string;
  payload: Record<string, unknown>;
  created_at?: string | null;
};

export type PicoWorkspace = {
  id: string;
  name: string;
  kind: string;
  note?: string;
  created_at?: string | null;
};

export type PicoSkillPolicy = {
  id: string;
  name: string;
  tools: string[];
  risk: string;
  requires_s7: boolean;
};

function authHeaders(): Record<string, string> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  try {
    const auth = getTokenHeader();
    if (typeof auth === 'string' && auth.startsWith('Bearer ')) {
      headers.Authorization = auth;
    } else if (typeof auth === 'string' && auth.length > 0) {
      headers.Authorization = auth.startsWith('Bearer') ? auth : `Bearer ${auth}`;
    }
  } catch {
    /* ignore */
  }
  return headers;
}

async function picoFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api/pico${path}`, {
    credentials: 'include',
    ...init,
    headers: {
      ...authHeaders(),
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

export async function getPicoArtifactContent(id: string, download = false): Promise<Blob> {
  const query = download ? '?download=true' : '';
  const res = await fetch(`/api/pico/v1/artifacts/${encodeURIComponent(id)}/content${query}`, {
    credentials: 'include',
    headers: authHeaders(),
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`pico ${res.status}: ${text.slice(0, 200)}`);
  }
  return res.blob();
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

export async function listPicoRunEvents(runId: string) {
  return picoFetch<{ events: PicoRunEvent[] }>(`/v1/runs/${runId}/events`);
}

export async function cancelPicoRun(runId: string) {
  return picoFetch<{ run: PicoRun }>(`/v1/runs/${runId}/cancel`, { method: 'POST' });
}

export async function cancelPicoTaskActiveRuns(taskId: string) {
  return picoFetch<{ runs: PicoRun[]; cancelled: number }>(
    `/v1/tasks/${taskId}/cancel-active`,
    { method: 'POST' },
  );
}

export async function retryPicoRun(runId: string) {
  return picoFetch<{ run: PicoRun; retried_from_run_id: string }>(`/v1/runs/${runId}/retry`, {
    method: 'POST',
  });
}

export async function listPicoWorkspaces() {
  return picoFetch<{ workspaces: PicoWorkspace[] }>(`/v1/workspaces`);
}

export async function listPicoSkillCatalog() {
  return picoFetch<{ skills: PicoSkillPolicy[] }>(`/v1/skills/catalog`);
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
  workspace_id?: string | null;
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
  workspace_id?: string;
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

export async function runPicoAutomation(id: string) {
  return picoFetch<{ automation: PicoAutomation; task: PicoTask; run: PicoRun }>(
    `/v1/automations/${id}/run`,
    { method: 'POST' },
  );
}

export async function deletePicoAutomation(id: string) {
  return picoFetch<{ ok: boolean }>(`/v1/automations/${id}`, { method: 'DELETE' });
}

export type PicoChange = {
  id: string;
  task_id?: string | null;
  run_id?: string | null;
  title: string;
  summary: string;
  payload?: Record<string, unknown>;
  status: 'proposed' | 'confirmed' | 'rejected';
  created_at?: string | null;
  confirmed_by?: string | null;
  confirmed_at?: string | null;
  audit?: unknown[];
};

export async function listPicoChanges(options?: {
  taskId?: string;
  status?: PicoChange['status'];
}) {
  const params = new URLSearchParams();
  if (options?.taskId) {
    params.set('task_id', options.taskId);
  }
  if (options?.status) {
    params.set('status', options.status);
  }
  const query = params.toString();
  return picoFetch<{ changes: PicoChange[] }>(`/v1/changes${query ? `?${query}` : ''}`);
}

export async function getPicoChange(id: string) {
  return picoFetch<{ change: PicoChange }>(`/v1/changes/${id}`);
}

export async function createPicoChange(body: {
  title: string;
  summary: string;
  payload?: Record<string, unknown>;
  task_id?: string;
  run_id?: string;
}) {
  return picoFetch<{ change: PicoChange }>(`/v1/changes`, {
    method: 'POST',
    body: JSON.stringify({
      title: body.title,
      summary: body.summary,
      payload: body.payload || {},
      task_id: body.task_id,
      run_id: body.run_id,
    }),
  });
}

export async function confirmPicoChange(id: string) {
  return picoFetch<{ change: PicoChange }>(`/v1/changes/${id}/confirm`, { method: 'POST' });
}

export async function rejectPicoChange(id: string) {
  return picoFetch<{ change: PicoChange }>(`/v1/changes/${id}/reject`, { method: 'POST' });
}
