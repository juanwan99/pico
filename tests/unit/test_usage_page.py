"""The authenticated My Usage page keeps filters and sorting in its links and form."""

import re
from datetime import UTC, datetime, timedelta
from html import unescape
from urllib.parse import parse_qs, urljoin, urlsplit

import pytest
from app import db
from app.auth import issue_test_token
from app.main import app
from app.settings import get_settings
from httpx import ASGITransport, AsyncClient


@pytest.fixture()
async def client(tmp_path, monkeypatch):
    monkeypatch.setenv("PICO_DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'usage.db'}")
    monkeypatch.setenv("PICO_JWT_SECRET", "test-secret-at-least-32-bytes-long!!")
    get_settings.cache_clear()
    db._engine = None
    db._Session = None
    await db.init_db()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client
    finally:
        assert db._engine is not None
        await db._engine.dispose()
        db._engine = None
        db._Session = None
        get_settings.cache_clear()


def _auth(school="school-a", member="m1", scopes=None):
    token = issue_test_token(school_id=school, membership_id=member, scopes=scopes)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
async def seeded(client):
    stamp = datetime(2026, 11, 27, 15, 30, tzinfo=UTC)
    async with db.session_factory()() as session:
        session.add_all([
            db.UsageEventRow(
                id=f"e{index:02d}", idempotency_key=f"e{index:02d}", run_id=f"run-{index:02d}",
                school_id="school-a", membership_id="m1",
                kind="llm" if index < 56 else ("search" if index % 2 else "image"),
                model="alpha" if index % 2 else 'beta < " &',
                created_at=stamp if index < 56 else stamp + timedelta(days=2 - index % 2),
                extra_json=('{"bill_to":"personal"}' if index >= 56 else
                            '{"bill_to":"school"}' if index % 2 else '{}'),
                prompt_tokens=100, completion_tokens=50, total_tokens=150,
            )
            for index in range(60)
        ])
        session.add_all([
            db.UsageEventRow(
                id=key, idempotency_key=key, run_id=key, school_id=school, membership_id=member,
                kind="image", model=key, created_at=stamp,
            )
            for key, school, member in [
                ("same-school-private", "school-a", "m2"),
                ("other-school-private", "school-b", "m1"),
            ]
        ])
        await session.commit()
    return client


async def _page(client, *, url="/v1/usage", params=None, headers=None):
    url = urljoin("/v1/usage", url)
    response = await client.get(url, params=params, headers=headers or _auth())
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/html")
    return response.text


def _runs(page):
    return re.findall(r"<td>(run-\d+)</td>", page)


def _link(page, text):
    match = re.search(r'<a\b[^>]*\bhref="([^"]+)"[^>]*>' + re.escape(text) + r"</a>", page)
    assert match is not None, text
    return unescape(match[1])


def _query(url):
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


async def test_filtered_pages_keep_conditions_and_changes_return_to_first(seeded):
    conditions = {
        "kind": ["llm"], "bill_to": ["member", "school"], "model": ["alpha", 'beta < " &'],
        "sort": "created_at", "direction": "asc",
    }
    first = await _page(seeded, params=conditions)
    assert _runs(first) == [f"run-{index:02d}" for index in range(50)]
    next_url = _link(first, "下一页")
    first_query = {
        key: value if isinstance(value, list) else [value] for key, value in conditions.items()
    }
    assert _query(next_url) == {**first_query, "page": ["2"], "after_id": ["e49"]}
    second = await _page(seeded, url=next_url)
    assert _runs(second) == [f"run-{index:02d}" for index in range(50, 56)]
    prev_url = _link(second, "上一页")
    assert _query(prev_url) == {**first_query, "before_id": ["e50"]}
    assert _runs(await _page(seeded, url=prev_url)) == _runs(first)
    assert "下一页" not in second
    assert _query(_link(second, "时间 ↑")) == {**first_query, "direction": ["desc"]}

    removed = _link(second, "记账：本人 ×")
    assert _query(removed) == {**first_query, "bill_to": ["school"]}
    assert _runs(await _page(seeded, url=removed)) == [
        f"run-{index:02d}" for index in range(1, 56, 2)
    ]
    assert _query(_link(second, "清除筛选")) == {"sort": ["created_at"], "direction": ["asc"]}
    assert "模型：beta &lt; &quot; &amp; ×" in second
    assert re.search(r'name="kind" value="search"', second)
    assert re.search(r'name="bill_to" value="personal"', second)


async def test_sort_cycle_and_default_order(seeded):
    default = await _page(seeded)
    by_time = [*range(56), 57, 59, 56, 58]
    expected = [f"run-{index:02d}" for index in by_time[::-1][:50]]
    assert _runs(default) == expected
    for label, ordering in [
        ("时间", by_time),
        ("类型", [56, 58, *range(56), 57, 59]),
    ]:
        ascending = await _page(seeded, url=_link(default, label))
        assert _runs(ascending) == [f"run-{index:02d}" for index in ordering[:50]]
        descending = await _page(seeded, url=_link(ascending, f"{label} ↑"))
        assert _runs(descending) == [f"run-{index:02d}" for index in ordering[::-1][:50]]
        assert _query(_link(descending, f"{label} ↓")) == {}
        assert _runs(await _page(seeded, url=_link(descending, f"{label} ↓"))) == expected


@pytest.mark.parametrize("params", [
    {"sort": "run_id", "direction": "asc"},
    {"sort": "kind", "direction": "up"},
])
async def test_invalid_sort_uses_default(seeded, params):
    page = await _page(seeded, params=params)
    assert _runs(page) == _runs(await _page(seeded))
    assert _query(_link(page, "类型")) == {"sort": ["kind"], "direction": ["asc"]}


async def test_filtered_empty_keeps_unfiltered_daily_summary(seeded):
    default = await _page(seeded)
    filtered = await _page(seeded, params={"kind": "search", "bill_to": "school"})
    assert "暂无符合筛选的记录" in filtered
    assert _query(_link(filtered, "清除筛选")) == {}
    assert "暂无用量记录" not in filtered
    daily = r"<h2>按日汇总（北京时间）</h2>\s*(<ul>.+?</ul>)"
    assert re.search(daily, filtered, re.DOTALL)[1] == re.search(daily, default, re.DOTALL)[1]


async def test_empty_account_and_scope_isolation(seeded):
    empty = await _page(seeded, headers=_auth(member="m3"), params={"kind": "llm"})
    assert "暂无用量记录" in empty and "暂无汇总" in empty
    assert "暂无符合筛选的记录" not in empty

    mine = await _page(
        seeded, headers=_auth(scopes=["ai:read", "ai:admin"]),
        params={"membership_id": "m2", "school_id": "school-b"},
    )
    assert "run-59" in mine
    assert "same-school-private" not in mine and "other-school-private" not in mine

    peer = await _page(seeded, headers=_auth(member="m2"))
    assert "same-school-private" in peer and "other-school-private" not in peer
    assert not _runs(peer)
    other_school = await _page(seeded, headers=_auth(school="school-b"))
    assert "other-school-private" in other_school and "same-school-private" not in other_school
    assert not _runs(other_school)
    assert (await seeded.get("/v1/usage")).status_code == 401
    denied = await seeded.get("/v1/usage", headers=_auth(scopes=["ai:run"]))
    assert denied.status_code == 403
    patrol = _auth(member="", scopes=["ai:read", "ai:school-run", "ai:steward-public"])
    denied = await seeded.get("/v1/usage", headers=patrol)
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "auth.steward_public_denied"
    for params in [
        {"after_id": "same-school-private", "page": 2},
        {"before_id": "other-school-private"},
    ]:
        invalid = await seeded.get("/v1/usage", params=params, headers=_auth())
        assert invalid.status_code == 400
        assert invalid.json()["detail"]["code"] == "usage.bad_cursor"


@pytest.mark.parametrize(("params", "ordered"), [
    ({}, [58, 56, 59, 57, *range(55, -1, -1)]),
    ({"sort": "kind", "direction": "asc"}, [56, 58, *range(56), 57, 59]),
])
async def test_pagination_stays_on_the_boundary_after_a_new_usage_event(seeded, params, ordered):
    first = await _page(seeded, params=params)
    expected = [f"run-{index:02d}" for index in ordered]
    assert _runs(first) == expected[:50]
    next_url = _link(first, "下一页")

    async with db.session_factory()() as writer:
        writer.add(db.UsageEventRow(
            id="e60", idempotency_key="e60", run_id="run-60",
            school_id="school-a", membership_id="m1", kind="api",
            created_at=datetime(2026, 11, 29, 15, 30, tzinfo=UTC),
        ))
        await writer.commit()

    second = await _page(seeded, url=next_url)
    assert _runs(second) == expected[50:]
    assert "下一页" not in second
    assert _runs(await _page(seeded, url=_link(second, "上一页"))) == expected[:50]
