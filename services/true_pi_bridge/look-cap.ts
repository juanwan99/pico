/**
 * pico#1296 look cap (workspace box only).
 *
 * The model renders its own file to pictures and `read`s them. Past 8 pictures,
 * or when a 3rd round starts (a look after a write/edit that followed 2 rounds
 * of looks), `read` on a picture returns one line of text instead of the image.
 * Mirror of EventMapState.look_call in pico_orchestrator/true_pi/events.py:
 * keep the two rules identical.
 */

import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const MAX_PICTURES = 8;
const MAX_ROUNDS = 2;
const CAP_TEXT = "看图额度用完。";
const IMAGE_EXT = [".png", ".jpg", ".jpeg", ".webp", ".gif"];

function lookRead(toolName: string, input: Record<string, unknown>): boolean {
  if (toolName !== "read") return false;
  const path = String(input.path ?? input.file_path ?? "");
  return IMAGE_EXT.some((ext) => path.toLowerCase().endsWith(ext)) && !path.includes("/attachments/");
}

export default function (pi: ExtensionAPI) {
  let pictures = 0;
  let rounds = 0;
  let changedSinceLook = true;
  const capped = new Set<string>();

  pi.on("tool_call", async (event) => {
    const input = (event.input ?? {}) as Record<string, unknown>;
    if (event.toolName === "write" || event.toolName === "edit") {
      changedSinceLook = true;
      return undefined;
    }
    if (!lookRead(event.toolName, input)) return undefined;
    const newRound = changedSinceLook;
    if (pictures >= MAX_PICTURES || (newRound && rounds >= MAX_ROUNDS)) {
      capped.add(event.toolCallId);
      return undefined;
    }
    if (newRound) rounds += 1;
    changedSinceLook = false;
    pictures += 1;
    return undefined;
  });

  pi.on("tool_result", async (event) => {
    if (!capped.has(event.toolCallId)) return undefined;
    capped.delete(event.toolCallId);
    return { content: [{ type: "text", text: CAP_TEXT }], isError: false };
  });
}
