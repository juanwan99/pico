"""Left-page mutation proposals for the edu sidebar (T-PICO-WIRE · Pico half).

edu-core#604: every school page reports ``affordances[]`` (what a human can
fill / tick / click, with the command behind it). The model may *propose* a
mutation against one of those ids; the school shell shows the confirm card and
runs its own command after the teacher confirms. Pico only owns the proposal
ledger and hands the ``mutations`` envelope back. It never executes, never
interprets ``params``, never invents an affordance the page did not report.

Thin adapter: parse → validate id → record. No page model, no rules engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pico_orchestrator.gateway import Principal, ToolError, ToolSpec

TOOL_NAME = "propose_page_mutation"
_MAX_AFFORDANCES = 400
_MAX_MUTATIONS = 200
_MAX_LABEL = 120
_MAX_PARAMS_CHARS = 20_000

TOOL_DESCRIPTION = (
    "Propose one change to the school page open on the left (fill / tick / click). "
    "Only ids from this page's affordances are accepted; the teacher confirms in the "
    "school shell and the school runs its own command. Nothing is written by this call. "
    "Args: affordance_id, params, label."
)

SIDEBAR_PAGE_HANDS_HINT = (
    "左边这一页报了能力表（affordances）：人能填、能勾、能点的都在里面，带 id 和当前值。"
    "要改左页，用 propose_page_mutation 按 id 一条条提案；人确认后由学校执行，你不要当成已改。"
    "改左页不要用 workspace_write_file / 生成文件冒充。批量就多提几条，部分做不了逐条说原因。"
    "能力表里没有的东西，如实说这页今天没有这只手，缺的是什么。"
)


def normalize_affordances(raw: Any) -> list[dict[str, Any]]:
    """Keep only what Pico needs to validate a proposal. Unknown keys pass through."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        aid = str(item.get("id") or item.get("affordanceId") or "").strip()
        if not aid or aid in seen:
            continue
        seen.add(aid)
        row = dict(item)
        row["id"] = aid
        out.append(row)
        if len(out) >= _MAX_AFFORDANCES:
            break
    return out


def _from_json_text(text: str | None) -> Any:
    raw = str(text or "").strip()
    if not raw:
        return None
    # System / user payloads may wrap JSON in prose; take the first object.
    start = raw.find("{")
    if start < 0:
        return None
    try:
        return json.loads(raw[start:])
    except json.JSONDecodeError:
        return None


def affordances_from_request(
    metadata: dict[str, Any] | None,
    client_system: str | None,
    prompt: str | None,
) -> list[dict[str, Any]]:
    """edu may carry the page's affordances in metadata, the 附属 system JSON,
    or the json_only user JSON. First non-empty source wins."""
    if isinstance(metadata, dict):
        found = normalize_affordances(metadata.get("affordances"))
        if found:
            return found
    for text in (client_system, prompt):
        parsed = _from_json_text(text)
        if isinstance(parsed, dict):
            found = normalize_affordances(parsed.get("affordances"))
            if found:
                return found
            page = parsed.get("page")
            if isinstance(page, dict):
                found = normalize_affordances(page.get("affordances"))
                if found:
                    return found
    return []


def page_title_from_request(client_system: str | None) -> str:
    parsed = _from_json_text(client_system)
    if isinstance(parsed, dict):
        page = parsed.get("page")
        if isinstance(page, dict):
            return str(page.get("title") or "").strip()[:120]
        return str(parsed.get("title") or "").strip()[:120]
    return ""


@dataclass
class PageMutationBook:
    """One run's proposals against one page. Lives only for the run."""

    affordances: list[dict[str, Any]]
    page_title: str = ""
    mutations: list[dict[str, Any]] = field(default_factory=list)

    def _lookup(self, affordance_id: str) -> dict[str, Any] | None:
        for row in self.affordances:
            if row.get("id") == affordance_id:
                return row
        return None

    def propose(self, args: dict[str, Any]) -> dict[str, Any]:
        aid = str(args.get("affordance_id") or args.get("affordanceId") or "").strip()
        if not aid:
            raise ToolError("page.affordance_required", "要先说改哪一处：affordance_id 不能为空。")
        row = self._lookup(aid)
        if row is None:
            raise ToolError(
                "page.affordance_unknown",
                "这一页的能力表里没有这个 id，今天没有这只手；把缺的说给老师。",
            )
        if row.get("writable") is False:
            raise ToolError(
                "page.affordance_readonly",
                f"「{row.get('label') or aid}」这个人现在没有写权，只能看。",
            )
        params = args.get("params")
        if params is None:
            params = {}
        if not isinstance(params, dict):
            raise ToolError("tool.invalid_arguments", "params 必须是对象。")
        if len(json.dumps(params, ensure_ascii=False)) > _MAX_PARAMS_CHARS:
            raise ToolError("tool.invalid_arguments", "params 太大，拆成多条提案。")
        if len(self.mutations) >= _MAX_MUTATIONS:
            raise ToolError("page.too_many_mutations", "这一轮提案已满，先让老师确认这一批。")
        label = str(args.get("label") or row.get("label") or aid).strip()[:_MAX_LABEL]
        mutation = {
            "affordanceId": aid,
            "params": params,
            "label": label,
            "tier": str(row.get("tier") or "work"),
            "status": "staged",
        }
        self.mutations.append(mutation)
        return {
            "staged": True,
            "affordanceId": aid,
            "label": label,
            "count": len(self.mutations),
            "note": "已记入提案，等老师在左边确认；未确认前学校什么都没改。",
        }

    def change_proposal(self) -> dict[str, Any] | None:
        """Pico ledger row (contracts/change-handoff.md). None when nothing staged."""
        if not self.mutations:
            return None
        title = f"页内改动提案 · {self.page_title}" if self.page_title else "页内改动提案"
        labels = [str(m.get("label") or m.get("affordanceId")) for m in self.mutations]
        summary = "；".join(labels[:8])
        if len(labels) > 8:
            summary += f"；…共 {len(labels)} 条"
        return {
            "proposal": {
                "title": title[:200],
                "summary": summary[:1000],
                "payload": {
                    "domain": "page",
                    "action": "mutations",
                    "page_title": self.page_title,
                    "mutations": list(self.mutations),
                },
                "status": "proposed",
            }
        }


def register_propose_page_mutation(gateway: Any, book: PageMutationBook | None) -> None:
    """Register the hand on this run's gateway. Without a book it fails closed."""

    async def handler(principal: Principal, args: dict[str, Any]) -> dict[str, Any]:
        del principal
        if book is None:
            raise ToolError(
                "page.no_affordances",
                "这一页没有报能力表，改不了左页；可以说清楚缺什么。",
            )
        return book.propose(args)

    gateway.register(
        ToolSpec(
            name=TOOL_NAME,
            description=TOOL_DESCRIPTION,
            handler=handler,
            school_scoped=False,
        )
    )
