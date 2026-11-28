"""Read-only My Usage page."""

from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Principal, require_person, require_scope
from app.db import get_session
from app.usage_ledger import (
    UsagePage,
    list_usage_page,
    summarize_usage,
    teacher_usage_event_dict,
)

router = APIRouter(dependencies=[Depends(require_person)])

_FILTER_LABELS = {"kind": "类型", "bill_to": "记账", "model": "模型"}
_PAYER_LABELS = {"school": "学校账", "personal": "我的接口", "member": "本人"}


def _filter_label(key: str, value: str) -> str:
    if key == "bill_to":
        return _PAYER_LABELS.get(value, value)
    return value or "—"


def _usage_query(
    filters: dict[str, list[str]],
    order: tuple[str, str] | None,
    page: int = 1,
    *,
    before_id: str | None = None,
    after_id: str | None = None,
) -> str:
    params = [(key, value) for key, values in filters.items() for value in values]
    if order:
        params.extend(zip(("sort", "direction"), order, strict=True))
    if page > 1:
        params.append(("page", str(page)))
        if before_id:
            params.append(("before_id", before_id))
    if after_id:
        params.append(("after_id", after_id))
    return "?" + escape(urlencode(params))


def _filter_controls(page: UsagePage, filters: dict[str, list[str]]) -> str:
    groups = []
    for key, label in _FILTER_LABELS.items():
        checks = []
        for value in page.options[key]:
            checked = " checked" if value in filters[key] else ""
            checks.append(
                f'<label><input type="checkbox" name="{key}" value="{escape(value)}"{checked}> '
                f"{escape(_filter_label(key, value))}</label>"
            )
        if checks:
            groups.append(
                f'<details name="usage-filters"><summary>{label}</summary>'
                f'<div class="options">{"".join(checks)}</div></details>'
            )
    form = ""
    if groups:
        hidden = ""
        if page.order:
            sort, direction = page.order
            hidden = (
                f'<input type="hidden" name="sort" value="{escape(sort)}">'
                f'<input type="hidden" name="direction" value="{escape(direction)}">'
            )
        form = (
            f'<form method="get" aria-label="筛选明细">{hidden}{"".join(groups)}'
            '<button type="submit">应用筛选</button></form>'
        )

    chips = []
    for key, values in filters.items():
        for value in dict.fromkeys(values):
            remaining = {**filters, key: [other for other in values if other != value]}
            url = _usage_query(remaining, page.order)
            label = escape(f"{_FILTER_LABELS[key]}：{_filter_label(key, value)}")
            chips.append(f'<a href="{url}" aria-label="移除{label}">{label} ×</a>')
    if chips:
        clear_url = _usage_query({}, page.order)
        chips.append(f'<a class="clear" href="{clear_url}">清除筛选</a>')
        form += f'<div class="chips">{"".join(chips)}</div>'
    return form


def _sort_header(
    key: str, label: str, page: UsagePage, filters: dict[str, list[str]],
) -> str:
    if page.order == (key, "asc"):
        url = _usage_query(filters, (key, "desc"))
        return f'<th aria-sort="ascending"><a href="{url}">{label} ↑</a></th>'
    if page.order == (key, "desc"):
        url = _usage_query(filters, None)
        return f'<th aria-sort="descending"><a href="{url}">{label} ↓</a></th>'
    url = _usage_query(filters, (key, "asc"))
    return f'<th><a href="{url}">{label}</a></th>'


def _pagination(page: UsagePage, filters: dict[str, list[str]]) -> str:
    if not page.total:
        return ""
    links = []
    if page.previous_id:
        url = _usage_query(filters, page.order, page.number - 1, before_id=page.previous_id)
        links.append(f'<a href="{url}">上一页</a>')
    links.append(f"<span>第 {page.number} 页 · 共 {page.total} 条</span>")
    if page.next_id:
        url = _usage_query(filters, page.order, page.number + 1, after_id=page.next_id)
        links.append(f'<a href="{url}">下一页</a>')
    return f'<nav aria-label="明细分页">{"".join(links)}</nav>'


def _usage_html(
    principal: Principal, summary: dict, page: UsagePage, filters: dict[str, list[str]],
) -> str:
    rows = []
    for row in page.rows:
        ev = teacher_usage_event_dict(row)
        points = ev["points"] or "—"
        bill = ev["extra"]["bill_to"]
        rows.append(
            "<tr>"
            f"<td>{escape(str(ev.get('created_at') or ''))}</td>"
            f"<td>{escape(str(ev.get('kind') or ''))}</td>"
            f"<td>{escape(str(ev.get('model') or '—'))}</td>"
            f"<td>{escape(_PAYER_LABELS[bill])}</td>"
            f"<td>{escape(points)}</td>"
            f"<td>{escape(str(ev.get('run_id') or '—'))}</td>"
            "</tr>"
        )
    if not rows:
        message = "暂无符合筛选的记录" if page.options["kind"] else "暂无用量记录（空态诚实）"
        rows.append(f'<tr><td colspan="6">{message}</td></tr>')
    body_rows = "\n".join(rows)

    day_bits = []
    for d in summary.get("days") or []:
        pts = d.get("points")
        pts_label = str(pts) if isinstance(pts, str) and pts else "—"
        bill = str(d.get("bill_to") or "member")
        day_bits.append(
            f"<li>{escape(str(d.get('day')))} · {escape(str(d.get('kind')))} · "
            f"{escape(_PAYER_LABELS.get(bill, bill))} · "
            f"{int(d.get('calls') or 0)} 次 · 积分 {escape(pts_label)}</li>"
        )
    days_html = "\n".join(day_bits) or "<li>暂无汇总</li>"
    school = escape(principal.school_id)
    member = escape(principal.membership_id)
    time_head = _sort_header("created_at", "时间", page, filters)
    kind_head = _sort_header("kind", "类型", page, filters)
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>我的用量</title>
<style>
body {{ font: 15px/1.55 system-ui, sans-serif; margin: 1.5rem; color: #182230; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border-bottom: 1px solid #dce2ea; padding: 0.45rem 0.75rem; text-align: left; }}
th {{ background: #f2f5f9; }}
tbody tr:nth-child(even) {{ background: #f8fafc; }}
td {{ overflow-wrap: anywhere; }}
.note {{ color: #475467; }}
a {{ color: #174d91; }}
form, .chips, nav {{ display: flex; align-items: center; flex-wrap: wrap; gap: 0.5rem; }}
form, .chips {{ margin-bottom: 0.75rem; }}
summary, button, .chips a, nav a {{
  padding: 0.25rem 0.65rem; border: 1px solid #b9c5d4; border-radius: 0.35rem;
}}
summary, button {{ background: #fff; cursor: pointer; font: inherit; color: inherit; }}
details {{ position: relative; }}
.options {{
  position: absolute; z-index: 1; background: #fff; border: 1px solid #b9c5d4;
  border-radius: 0.35rem; padding: 0.5rem; margin-top: 0.25rem;
  min-width: max-content; max-height: 16rem; overflow: auto;
}}
.options label {{ display: block; padding: 0.2rem; cursor: pointer; }}
.chips a {{ background: #eef4fc; text-decoration: none; }}
.chips .clear {{ background: #fff; }}
nav {{ justify-content: flex-end; margin-top: 0.8rem; }}
</style></head><body>
<h1>我的用量</h1>
<p class="note">统计/管理 · <strong>不做钱</strong>（无价格、无扣款）。账号 {school} / {member}</p>
<h2>按日汇总（北京时间）</h2>
<ul>{days_html}</ul>
<h2>明细</h2>
{_filter_controls(page, filters)}
<table>
<thead><tr>{time_head}{kind_head}<th>模型</th><th>记账</th><th>积分</th><th>run</th></tr></thead>
<tbody>
{body_rows}
</tbody>
</table>
{_pagination(page, filters)}
</body></html>
"""


@router.get("/v1/usage", response_class=HTMLResponse)
async def my_usage_page(
    principal: Principal = Depends(require_scope("ai:read")),
    session: AsyncSession = Depends(get_session),
    kind: list[str] | None = Query(default=None),
    bill_to: list[str] | None = Query(default=None),
    model: list[str] | None = Query(default=None),
    sort: str | None = None,
    direction: str | None = None,
    page: int = Query(default=1, ge=1),
    before_id: str | None = None,
    after_id: str | None = None,
) -> HTMLResponse:
    filters = {"kind": kind or [], "bill_to": bill_to or [], "model": model or []}
    # Keep both reads on the same SQLite snapshot, including for an empty account.
    async with session.begin_nested():
        details = await list_usage_page(
            session, principal, filters=filters, sort=sort, direction=direction, page=page,
            before_id=before_id, after_id=after_id,
        )
        summary = await summarize_usage(session, principal)
    return HTMLResponse(_usage_html(principal, summary, details, filters))
