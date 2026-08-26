/**
 * Pico thin-bridge extension for true Pi RPC mode.
 *
 * Registers only the allowlisted gateway tools. Each tool POSTs to the
 * per-run localhost tool server started by Python (PICO_TRUE_PI_TOOL_URL).
 *
 * Launch: pi --mode rpc --no-builtin-tools -e ./pico-gateway-tools.ts ...
 *
 * FORBIDDEN: bash, arbitrary FS, MCP, delivery_policy logic.
 */

import { Type } from "@mariozechner/pi-ai";
import type { ExtensionAPI } from "@mariozechner/pi-coding-agent";

const TOOL_URL = (process.env.PICO_TRUE_PI_TOOL_URL || "").replace(/\/$/, "");
const TOOL_TOKEN = process.env.PICO_TRUE_PI_TOOL_TOKEN || "";
const RUN_ID = process.env.PICO_TRUE_PI_RUN_ID || "";

const ALLOWED = [
  "workspace_list_files",
  "workspace_read_file",
  "workspace_write_file",
  "generate_html_document",
  "generate_docx_document",
  "generate_pptx_document",
  "edit_docx_document",
  "edit_pptx_document",
  "render_document",
  "inspect_document",
  "verify_document",
  "generate_image",
  "verify_html_document",
  "web_search",
  "web_fetch",
  "kb_search",
  "sandbox_preview_inspect",
  "sandbox_workspace_exec",
  "sandbox_browser_open",
  "sandbox_browser_screenshot",
  "sandbox_document_open",
] as const;

type ToolName = (typeof ALLOWED)[number];

async function callGateway(
  tool: ToolName,
  args: Record<string, unknown>,
  signal?: AbortSignal,
): Promise<{ ok: boolean; result?: unknown; error?: string; code?: string }> {
  if (!TOOL_URL || !TOOL_TOKEN) {
    return {
      ok: false,
      code: "bridge.unconfigured",
      error: "PICO_TRUE_PI_TOOL_URL / TOKEN not set",
    };
  }
  const res = await fetch(`${TOOL_URL}/v1/tool`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${TOOL_TOKEN}`,
      "X-Pico-Run-Id": RUN_ID,
    },
    body: JSON.stringify({ tool, arguments: args }),
    signal,
  });
  let body: any = null;
  try {
    body = await res.json();
  } catch {
    return { ok: false, code: "bridge.bad_json", error: `HTTP ${res.status}` };
  }
  if (!res.ok || !body?.ok) {
    return {
      ok: false,
      code: body?.code || `http.${res.status}`,
      error: body?.error || `tool failed HTTP ${res.status}`,
      result: body,
    };
  }
  return { ok: true, result: body.result };
}

function textResult(payload: unknown) {
  const text =
    typeof payload === "string" ? payload : JSON.stringify(payload ?? {}, null, 0);
  return {
    content: [{ type: "text" as const, text }],
    details: payload,
  };
}

function registerTool(
  pi: ExtensionAPI,
  name: ToolName,
  description: string,
  parameters: ReturnType<typeof Type.Object>,
) {
  pi.registerTool({
    name,
    label: name,
    description,
    parameters,
    async execute(_toolCallId, params, signal) {
      const args = (params || {}) as Record<string, unknown>;
      const out = await callGateway(name, args, signal);
      if (!out.ok) {
        return textResult({ error: out.error, code: out.code, tool: name });
      }
      return textResult(out.result ?? {});
    },
  });
}

export default function (pi: ExtensionAPI) {
  // Free-form object args — Pico gateway validates per tool.
  const AnyArgs = Type.Object({}, { additionalProperties: true });

  registerTool(
    pi,
    "workspace_list_files",
    "List Artifacts owned by the current membership (Pico ledger).",
    Type.Object({ limit: Type.Optional(Type.Number()) }, { additionalProperties: true }),
  );
  registerTool(
    pi,
    "workspace_read_file",
    "Read one Artifact by id or title from the Pico ledger.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "workspace_write_file",
    "Write a real downloadable text Artifact into the Pico ledger.",
    Type.Object(
      {
        title: Type.String(),
        content: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "generate_html_document",
    "Create a real .html Artifact (Pico gateway).",
    Type.Object(
      {
        title: Type.String(),
        marker: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "generate_docx_document",
    "Create a real .docx Artifact (Pico gateway).",
    Type.Object(
      {
        title: Type.String(),
        marker: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "generate_pptx_document",
    "Create a real .pptx Artifact (Pico gateway).",
    Type.Object(
      {
        title: Type.String(),
        marker: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "edit_docx_document",
    "Edit an already uploaded .docx in the Pico ledger (python-docx). Other paragraphs stay.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        paragraph_index: Type.Optional(Type.Number()),
        text: Type.Optional(Type.String()),
        output_title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "edit_pptx_document",
    "Edit an already uploaded .pptx in the Pico ledger (python-pptx). Other slides stay.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        slide_index: Type.Optional(Type.Number()),
        new_title: Type.Optional(Type.String()),
        output_title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "render_document",
    "Create Word/PPT from pico.office.spec/v1 (tables/images inside the file).",
    AnyArgs,
  );
  registerTool(
    pi,
    "inspect_document",
    "Read paragraph/slide/table/image indexes of a ledger Word/PPT. Call before edit.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        kind: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "verify_document",
    "Fail-closed OOXML check for a ledger Word/PPT.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        kind: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "generate_image",
    "Create one downloadable png/jpg via SiliconFlow HTTPS. Never invent an image on failure.",
    Type.Object(
      {
        prompt: Type.String(),
        title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "verify_html_document",
    "Static HTML structure self-check via Pico gateway (not browser QA).",
    AnyArgs,
  );
  registerTool(
    pi,
    "web_search",
    "Search the public web via DeepSeek official web_search (Pico gateway). Returns sources or honest 未检索.",
    Type.Object(
      {
        query: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "kb_search",
    "Search this membership's indexed materials (Meili projection; keyword or hybrid). Call only when the teacher asks about school materials. Being listed does not mean you must call. Returns excerpts + sources (title/artifact_id/snippet) or honest_miss. Never invent content.",
    Type.Object(
      {
        query: Type.String(),
        limit: Type.Optional(Type.Number()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "web_fetch",
    "Read one public http(s) page into text via Pico gateway. Denies intranet/metadata/admin hosts.",
    Type.Object(
      {
        url: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_preview_inspect",
    "See THIS run's HTML preview (title/h1). Not public crawl. Not intranet.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        preview_url: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_workspace_exec",
    "Parse HTML or Python inside this run's isolated workspace. Timeout-killed. No bash.",
    Type.Object(
      {
        html: Type.Optional(Type.String()),
        source: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_browser_open",
    "Open a PUBLIC page in the isolated sandbox browser (human-in-the-loop login). Denies intranet/metadata/18765. WeChat/教务 are not required to succeed. Never send passwords in chat.",
    Type.Object(
      {
        url: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_browser_screenshot",
    "Capture the current isolated sandbox browser screen. Teacher logs in on the view page; do not ask for passwords in chat.",
    Type.Object(
      {
        session_id: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_document_open",
    "Open a Word/Calc/Impress file in sidecar LibreOffice. Word is Word — do not convert to PDF or HTML.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        filename: Type.Optional(Type.String()),
        kind: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
}
