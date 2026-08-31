/**
 * @askjo/pi-mem@1.2.0 — Pico thin adapter.
 *
 * Upstream file tools + context inject. No TUI dashboard / git / 24h LLM.
 * See SOURCE.txt.
 */

import { Type } from "@earendil-works/pi-ai";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import * as fs from "node:fs";
import * as path from "node:path";

import {
  type MemoryConfig,
  buildConfig,
  todayStr,
  nowTimestamp,
  shortSessionId,
  readFileSafe,
  dailyPath,
  ensureDirs,
  parseScratchpad,
  serializeScratchpad,
  buildMemoryContext,
  readMemoryFile,
  searchMemory,
} from "./lib.ts";

const config: MemoryConfig = buildConfig();

function sid(ctx: { sessionManager?: { getSessionId?: () => string } } | undefined): string {
  try {
    return shortSessionId(String(ctx?.sessionManager?.getSessionId?.() || "pico"));
  } catch {
    return "pico";
  }
}

export default function picoPiMem(pi: ExtensionAPI): void {
  pi.on("context", async (event: { messages: unknown[] }) => {
    const memoryContext = buildMemoryContext(config);
    const memoryInstructions = [
      "## Memory",
      "The following memory files have been loaded. Use the memory_write tool to persist important information.",
      "- Decisions, preferences, and durable facts → MEMORY.md",
      "- Day-to-day notes and running context → daily/<YYYY-MM-DD>.md",
      "- Things to fix later or keep in mind → scratchpad tool",
      "- Scratchpad is NOT auto-loaded. Use memory_read(target='scratchpad') to fetch it when needed.",
      '- If someone says "remember this," write it immediately.',
      "",
      memoryContext,
    ].join("\n");
    return {
      messages: [
        ...event.messages,
        {
          role: "user" as const,
          content: `<pi-mem-injected>\n${memoryInstructions}\n</pi-mem-injected>`,
          timestamp: Date.now(),
        },
      ],
    };
  });

  pi.registerTool({
    name: "memory_write",
    label: "Memory Write",
    description:
      "Write to memory files. target=long_term (MEMORY.md), daily, or note. Use when the user asks you to remember something.",
    parameters: Type.Object(
      {
        target: Type.String({ description: "long_term | daily | note" }),
        content: Type.String({ description: "Markdown to write" }),
        mode: Type.Optional(Type.String({ description: "append | overwrite" })),
        filename: Type.Optional(Type.String({ description: "Required for note" })),
      },
      { additionalProperties: true },
    ),
    async execute(_id: string, params: Record<string, unknown>, _signal: unknown, _onUpdate: unknown, ctx: unknown) {
      ensureDirs(config);
      const target = String(params.target || "long_term");
      const content = String(params.content || "");
      const mode = String(params.mode || "append");
      const filename = params.filename ? String(params.filename) : "";
      const session = sid(ctx as { sessionManager?: { getSessionId?: () => string } });
      const ts = nowTimestamp();
      if (!content.trim()) {
        return { content: [{ type: "text", text: "Error: content required." }], details: {} };
      }
      if (target === "note") {
        if (!filename) {
          return { content: [{ type: "text", text: "Error: filename required for note." }], details: {} };
        }
        const safe = path.basename(filename);
        const filePath = path.join(config.notesDir, safe);
        const existing = readFileSafe(filePath) ?? "";
        if (mode === "overwrite") {
          fs.writeFileSync(filePath, `<!-- last updated: ${ts} [${session}] -->\n${content}`, "utf-8");
          return { content: [{ type: "text", text: `Wrote notes/${safe}` }], details: { path: filePath } };
        }
        const separator = existing.trim() ? "\n\n" : "";
        fs.writeFileSync(filePath, `${existing}${separator}<!-- ${ts} [${session}] -->\n${content}`, "utf-8");
        return { content: [{ type: "text", text: `Appended to notes/${safe}` }], details: { path: filePath } };
      }
      if (target === "daily") {
        const date = todayStr(config.timezone);
        const filePath = dailyPath(config.dailyDir, date);
        const existing = readFileSafe(filePath) ?? "";
        const separator = existing.trim() ? "\n\n" : "";
        fs.writeFileSync(filePath, `${existing}${separator}<!-- ${ts} [${session}] -->\n${content}`, "utf-8");
        return { content: [{ type: "text", text: `Appended to daily/${date}.md` }], details: { path: filePath } };
      }
      const existing = readFileSafe(config.memoryFile) ?? "";
      if (mode === "overwrite") {
        fs.writeFileSync(config.memoryFile, `<!-- last updated: ${ts} [${session}] -->\n${content}`, "utf-8");
        return { content: [{ type: "text", text: "Overwrote MEMORY.md" }], details: { path: config.memoryFile } };
      }
      const separator = existing.trim() ? "\n\n" : "";
      fs.writeFileSync(config.memoryFile, `${existing}${separator}<!-- ${ts} [${session}] -->\n${content}`, "utf-8");
      return { content: [{ type: "text", text: "Appended to MEMORY.md" }], details: { path: config.memoryFile } };
    },
  });

  pi.registerTool({
    name: "scratchpad",
    label: "Scratchpad",
    description: "Checklist. action=add|done|undo|clear_done|list.",
    parameters: Type.Object(
      {
        action: Type.String({ description: "add | done | undo | clear_done | list" }),
        text: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
    async execute(_id: string, params: Record<string, unknown>) {
      ensureDirs(config);
      const action = String(params.action || "list");
      const text = params.text ? String(params.text) : "";
      const existing = readFileSafe(config.scratchpadFile) ?? "";
      let items = parseScratchpad(existing);
      if (action === "list") {
        if (items.length === 0) {
          return { content: [{ type: "text", text: "Scratchpad is empty." }], details: {} };
        }
        return { content: [{ type: "text", text: serializeScratchpad(items) }], details: {} };
      }
      if (action === "add") {
        if (!text) {
          return { content: [{ type: "text", text: "Error: text required for add." }], details: {} };
        }
        items.push({ done: false, text, meta: `<!-- ${nowTimestamp()} -->` });
        fs.writeFileSync(config.scratchpadFile, serializeScratchpad(items), "utf-8");
        return { content: [{ type: "text", text: `Added: - [ ] ${text}` }], details: {} };
      }
      if (action === "done" || action === "undo") {
        if (!text) {
          return { content: [{ type: "text", text: `Error: text required for ${action}.` }], details: {} };
        }
        const needle = text.toLowerCase();
        const targetDone = action === "done";
        const hit = items.find((item) => item.done !== targetDone && item.text.toLowerCase().includes(needle));
        if (!hit) {
          return { content: [{ type: "text", text: `No matching item for: "${text}"` }], details: {} };
        }
        hit.done = targetDone;
        fs.writeFileSync(config.scratchpadFile, serializeScratchpad(items), "utf-8");
        return { content: [{ type: "text", text: "Updated." }], details: {} };
      }
      if (action === "clear_done") {
        items = items.filter((item) => !item.done);
        fs.writeFileSync(config.scratchpadFile, serializeScratchpad(items), "utf-8");
        return { content: [{ type: "text", text: "Cleared done items." }], details: {} };
      }
      return { content: [{ type: "text", text: `Unknown action: ${action}` }], details: {} };
    },
  });

  pi.registerTool({
    name: "memory_read",
    label: "Memory Read",
    description: "Read memory. target=long_term|scratchpad|daily|file|note|list.",
    parameters: Type.Object(
      {
        target: Type.String({ description: "long_term | scratchpad | daily | file | note | list" }),
        date: Type.Optional(Type.String()),
        filename: Type.Optional(Type.String()),
      },
      { additionalProperties: true },
    ),
    async execute(_id: string, params: Record<string, unknown>) {
      ensureDirs(config);
      const target = String(params.target || "long_term");
      const filename = params.filename ? String(params.filename) : "";
      if (target === "list") {
        const names: string[] = [];
        try {
          names.push(...fs.readdirSync(config.memoryDir).filter((f) => f.endsWith(".md")).sort());
        } catch {
          /* empty */
        }
        return {
          content: [{ type: "text", text: names.length ? names.map((n) => `- ${n}`).join("\n") : "Memory directory is empty." }],
          details: {},
        };
      }
      if (target === "file") {
        if (!filename) {
          return { content: [{ type: "text", text: "Error: filename required." }], details: {} };
        }
        const result = readMemoryFile(config, filename);
        return { content: [{ type: "text", text: result.text }], details: result.details };
      }
      if (target === "note") {
        if (!filename) {
          return { content: [{ type: "text", text: "Error: filename required." }], details: {} };
        }
        const safe = path.basename(filename);
        const content = readFileSafe(path.join(config.notesDir, safe));
        return { content: [{ type: "text", text: content || `Note not found: notes/${safe}` }], details: {} };
      }
      if (target === "daily") {
        const d = params.date ? String(params.date) : todayStr(config.timezone);
        const content = readFileSafe(dailyPath(config.dailyDir, d));
        return { content: [{ type: "text", text: content || `No daily log for ${d}.` }], details: {} };
      }
      if (target === "scratchpad") {
        const content = readFileSafe(config.scratchpadFile);
        return { content: [{ type: "text", text: content?.trim() ? content : "SCRATCHPAD.md is empty." }], details: {} };
      }
      const content = readFileSafe(config.memoryFile);
      return { content: [{ type: "text", text: content || "MEMORY.md is empty." }], details: {} };
    },
  });

  pi.registerTool({
    name: "memory_search",
    label: "Memory Search",
    description: "Keyword search across MEMORY.md, daily logs, and notes.",
    parameters: Type.Object(
      {
        query: Type.String(),
        max_results: Type.Optional(Type.Number()),
      },
      { additionalProperties: true },
    ),
    async execute(_id: string, params: Record<string, unknown>) {
      ensureDirs(config);
      const query = String(params.query || "").trim();
      if (!query) {
        return { content: [{ type: "text", text: "Error: query required." }], details: {} };
      }
      const result = searchMemory(config, query, Number(params.max_results || 20));
      if (result.fileMatches.length === 0 && result.lineResults.length === 0) {
        return { content: [{ type: "text", text: `No results for "${query}".` }], details: {} };
      }
      const parts: string[] = [];
      if (result.fileMatches.length) {
        parts.push(`Files:\n${result.fileMatches.map((f) => `- ${f}`).join("\n")}`);
      }
      if (result.lineResults.length) {
        parts.push(`Content:\n${result.lineResults.map((r) => `${r.file}:${r.line}: ${r.text}`).join("\n")}`);
      }
      return { content: [{ type: "text", text: parts.join("\n\n") }], details: {} };
    },
  });
}
