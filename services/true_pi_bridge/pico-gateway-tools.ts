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
  "sandbox_pptx_lib",
  "generate_xlsx_document",
  "edit_docx_document",
  "edit_pptx_document",
  "edit_xlsx_document",
  "render_document",
  "inspect_document",
  "verify_document",
  "generate_image",
  "generate_diagram",
  "verify_html_document",
  "web_search",
  "web_fetch",
  "kb_search",
  "sandbox_preview_inspect",
  "sandbox_workspace_exec",
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
    "Read one Artifact by id or title from the Pico ledger (including this-turn chat paperclip documents).",
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
    "Create a real .html Artifact (Pico gateway). Page must run offline: inline CSS/JS/canvas only. No CDN, no import or script-src of Three.js/Chart.js/ECharts/KaTeX, no https or //cdn images (use data: URLs), no window.THREE / new Chart / echarts.init. The tool fails closed if the page still needs the network or those engines. Result includes an observation of what landed. ok is not finished.",
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
    "Create a real .docx Artifact (Pico gateway). Result includes an observation of what landed. ok is not finished.",
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
    "Create a real .pptx Artifact via spec/blocks on stock python-pptx layouts (title, bullets, table, theme colors). Sibling of sandbox_pptx_lib (isolated python-pptx) — pick from the teacher's ask, not a scene word. Free shapes / color blocks / full-bleed geometry are not this tool; write python-pptx in sandbox_pptx_lib. Same title replaces the file the teacher opens. Read observation.outline.images after. A missing image_artifact_id skips that picture; the file still lands. blocks[].type cover/content/title/page (or omitted) are slides — not a new spec field. To embed a picture/diagram, first generate_image or generate_diagram, then pass that artifact id as image_artifact_id on the slide in spec/blocks. [image:…] in body does not embed. Pictures already inside the file are not separate downloads. ok is not finished.",
    Type.Object(
      {
        title: Type.String(),
        marker: Type.Optional(Type.String()),
        body: Type.Optional(Type.String()),
        spec: Type.Optional(Type.Object({}, { additionalProperties: true })),
        blocks: Type.Optional(
          Type.Array(
            Type.Object(
              {
                type: Type.Optional(Type.String()),
                title: Type.Optional(Type.String()),
                bullets: Type.Optional(Type.Array(Type.String())),
                image_artifact_id: Type.Optional(Type.String()),
              },
              { additionalProperties: true },
            ),
          ),
        ),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "generate_xlsx_document",
    "Create a real .xlsx Artifact (Pico gateway). Result includes an observation of what landed. ok is not finished.",
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
    "Edit an already uploaded .docx. Result includes an observation of what landed. ok is not finished.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        paragraph_index: Type.Optional(Type.Number()),
        text: Type.Optional(Type.String()),
        comment: Type.Optional(Type.String()),
        output_title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "edit_pptx_document",
    "Edit an already uploaded .pptx. Result includes an observation of what landed. ok is not finished.",
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
    "edit_xlsx_document",
    "Edit an already uploaded .xlsx. Result includes an observation of what landed. ok is not finished.",
    Type.Object(
      {
        artifact_id: Type.Optional(Type.String()),
        title: Type.Optional(Type.String()),
        cell: Type.Optional(Type.String()),
        value: Type.Optional(Type.String()),
        sheet: Type.Optional(Type.String()),
        output_title: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
  registerTool(
    pi,
    "render_document",
    "Create Word/PPT/Excel from pico.office.spec/v1 (tables/images/formulas inside the file).",
    AnyArgs,
  );
  registerTool(
    pi,
    "inspect_document",
    "Read paragraph/slide/sheet/comment indexes of a ledger Word/PPT/Excel. Embedded pictures are kept so the teacher's next question can see them. Call before edit.",
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
    "Fail-closed OOXML check for a ledger Word/PPT/Excel. Old .doc/.ppt/.xls fail honestly.",
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
    "Create one png/jpg via the configured HTTPS image API. To place it inside Word/PPT, pass the returned artifact id as image_artifact_id on spec. Do not also hand it to the teacher as a separate download when it is already inside the file. Never invent pixels on failure.",
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
    "Draw one structure diagram (flowchart, sequence, org) from mermaid source into a PNG Artifact. Sibling of generate_image — they do not veto each other. kind=d2 is not wired. Never invent a diagram on failure. To place it in Word/PPT, pass the artifact id as image_artifact_id. Do not also hand it to the teacher as a separate download when it is already inside the file.",
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
    "sandbox_pptx_lib",
    "Isolated python-pptx (not host bash, not a second Office OS). Sibling of generate_pptx_document — not the only PPT path. from pptx import Presentation, Inches, Pt, RGBColor is allowed (Inches/Pt also on pptx). add_shape and RGBColor color blocks are this tool. from pathlib import Path is a stub (mkdir ignored; no host files). prs.save is routed to the ledger (same as save_deck). Do not import os. add_title_slide(prs, title, subtitle, image=IMAGE_PATHS[0]); add_table(prs=prs, rows=grid); IMAGE_PATHS[0] is the first picture. Must add slides then save_deck(prs) or prs.save. Empty Presentation();save_deck fails — do not send a placeholder. A missing image_artifact_ids entry is skipped.",
    Type.Object(
      {
        source: Type.String(),
        title: Type.Optional(Type.String()),
        image_artifact_ids: Type.Optional(Type.Array(Type.String())),
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
    "Publish an existing HTML artifact to a public URL. Visitors can open it without login. Forms may POST JSON to the page collect path; entries land in the publisher archive.",
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
    "Revoke a published HTML page. The public URL and collect path return 404.",
    Type.Object(
      {
        page_id: Type.Optional(Type.String()),
        artifact_id: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
  );
}
