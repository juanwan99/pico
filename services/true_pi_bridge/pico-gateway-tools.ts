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

import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const TOOL_URL = (process.env.PICO_TRUE_PI_TOOL_URL || "").replace(/\/$/, "");
const TOOL_TOKEN = process.env.PICO_TRUE_PI_TOOL_TOKEN || "";
const RUN_ID = process.env.PICO_TRUE_PI_RUN_ID || "";

const ALLOWED = [
  "workspace_list_files",
  "workspace_read_file",
  "workspace_write_file",
  "generate_html_document",
  "sandbox_office_lib",
  "read_office_skill",
  "generate_image",
  "generate_diagram",
  "verify_html_document",
  "web_search",
  "web_fetch",
  "kb_search",
  "ask_user",
  "sandbox_preview_inspect",
  "sandbox_browser_open",
  "sandbox_browser_screenshot",
  "sandbox_document_open",
  "publish_html_page",
  "unpublish_html_page",
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

function visibleAllowlist(): Set<ToolName> {
  const raw = (process.env.PICO_TRUE_PI_VISIBLE_TOOLS || "").trim();
  if (!raw) {
    return new Set(ALLOWED);
  }
  const want = new Set(
    raw
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
  );
  return new Set(ALLOWED.filter((name) => want.has(name)));
}

function registerTool(
  pi: ExtensionAPI,
  name: ToolName,
  description: string,
  parameters: ReturnType<typeof Type.Object>,
) {
  if (!visibleAllowlist().has(name)) {
    return;
  }
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
    "Read one Artifact by id or title from the Pico ledger (including this-turn chat paperclip documents). PDF/docx/xlsx/pptx originals are already on this turn's model file channel; this tool is the ledger copy. Old .doc/.ppt/.xls are converted to OOXML first. Unread office means conversion or extract failed — do not ask the teacher to re-upload, re-save, or send screenshots. png/jpg stay metadata only — no pixels in the tool JSON. Pass a picture artifact id to a document tool to embed.",
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
    "Create a real .html Artifact (Pico gateway). A semantic classless visual base is already inlined — write header/main/article/nav/table/form; extra CSS only for one accent. Do not name the stylesheet to the teacher. Page must run offline: inline CSS/JS/SVG (canvas allowed, not required). No CDN, no import or script-src of Three.js/Chart.js/ECharts/KaTeX, no https or //cdn images, no window.THREE / new Chart / echarts.init. To embed a ledger picture, set img src to pico-artifact:<artifact_id> (or pico-artifact:0 with image_artifact_ids). Pico inlines data: URLs when the teacher opens or downloads. Do not paste base64. A missing id skips that picture; the page still lands. The tool fails closed if the page still needs the network or those engines, or if an inline script has unmatched brackets — keep a complete inline page; do not dumb it down on purpose. Result includes an observation of what landed. ok is not finished. Public publishing is not a Pico capability — do not follow with publish_html_page; school pages apply through Edu.",
    Type.Object(
      {
        title: Type.String(),
        marker: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
        image_artifact_ids: Type.Optional(Type.Array(Type.String())),
      },
      { additionalProperties: true },
    ),
  );









  registerTool(
    pi,
    "generate_image",
    "Create one png/jpg via the configured HTTPS image API. To place it inside Word/PPT, pass the returned artifact id as image_artifact_ids on sandbox_office_lib. To place it inside HTML, set img src to pico-artifact:<id>. Do not paste base64. Do not also hand it to the teacher as a separate download when it is already inside the file. Never invent pixels on failure.",
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
    "generate_diagram",
    "Draw one structure diagram (flowchart, sequence, org) from mermaid source into a PNG Artifact. Sibling of generate_image — they do not veto each other. kind=d2 is not wired. Never invent a diagram on failure. To place it in Word/PPT, pass the artifact id as image_artifact_ids on sandbox_office_lib. Do not also hand it to the teacher as a separate download when it is already inside the file.",
    Type.Object(
      {
        source: Type.String(),
        kind: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "verify_html_document",
    "Static HTML structure self-check via Pico gateway (not browser QA). Fails when the page loads scripts, ES imports, styles, images, or media from http(s).",
    AnyArgs,
  );
  registerTool(
    pi,
    "web_search",
    "Search the public web via the Pico gateway. Returns sources or honest 未检索.",
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
    "ask_user",
    "When the teacher did not say what they want done, ask a short multiple-choice question (2–5 options) and wait. After they pick, continue the same turn. If they already named what to make (a picture, a page, a file, or several of those), do that work — a missing topic, style, or caption is not a reason to call this; pick a simple default. Picking a default so you can start is not inventing a goal. Do not use this to choose a topic. Do not use this to quiz about a third-party form backend. Pico cannot hang a public URL; school pages apply through Edu.",
    Type.Object(
      {
        question: Type.String(),
        options: Type.Array(Type.String()),
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
    "See THIS run's HTML preview (title/h1) and keep a PNG so the teacher's next question can see the page. Not public crawl. Not intranet.",
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
    "read_office_skill",
    "On-demand office craft (docx / xlsx / pptx). SYSTEM only lists name+when. This returns the full python-docx / openpyxl / python-pptx craft. Not LibreChat Skills. After reading, write with sandbox_office_lib (kind matches id). Change an existing file with artifact_id. The office write path is sandbox_office_lib only.",
    Type.Object(
      {
        id: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "sandbox_office_lib",
    "The office write path: run a Python script inside the isolated pico-office container (no network, throwaway workdir). Full Python 3.12 with python-docx / openpyxl / python-pptx, the whole standard library (csv, json, re, os, pathlib...), pandas, Pillow, matplotlib, and soffice for legacy conversion. kind=docx|xlsx|pptx (or infer from title suffix). Names already in scope: INPUT_PATH (the artifact_id original, any type: xlsx/docx/pptx/csv/txt/json/png), OUTPUT_PATH, IMAGE_PATHS[i] (from image_artifact_ids), load_doc/load_book/load_deck, save_doc/save_book/save_deck, add_title_slide/add_content_slide/add_table. Write the result to OUTPUT_PATH (or any *.kind in the workdir; the newest is collected). Empty shells fail. On failure you get stderr back — fix the script and call again. One call = one output file.",
    Type.Object(
      {
        source: Type.String(),
        kind: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        artifact_id: Type.Optional(Type.String()),
        image_artifact_ids: Type.Optional(Type.Array(Type.String())),
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
    "Capture the current isolated sandbox browser screen and keep the PNG so the teacher's next question can see the page. Teacher logs in on the view page; do not ask for passwords in chat.",
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
    "Open a Word/Excel/PPT file in the sandbox as a page/slide content box (not LibreOffice chrome). Needs artifact_id, a disk filename, or body. Does not invent a file. The file stays OOXML — do not convert to PDF.",
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
  registerTool(
    pi,
    "publish_html_page",
    "Not a Pico capability. Public school pages go through Edu apply + school-admin approval. This tool always fails closed and never creates pico.aivia.asia/p links. Generate HTML instead.",
    Type.Object(
      {
        artifact_id: Type.String(),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "unpublish_html_page",
    "Revoke a leftover Pico /p/{id} page if one still exists. Pico does not publish.",
    Type.Object(
      {
        page_id: Type.Optional(Type.String()),
        artifact_id: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
}
