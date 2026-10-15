"""The one door to the model relay (pico#1271).

Every request Pico sends to New API goes through here: direct chat
(``provider.stream_chat``), Pi steps through the run proxy (``ws_proxy_router``,
``llm_pass_router``), embeddings / rerank (``meili_kb``) and images
(``image_generate``). The rules live in one place:

* **Budget.** One logical call sends at most ``CALL_BUDGET`` requests: the
  first, one hedge, one retry or model switch — all counted together. Before
  this, retries nested (Pi 8× → proxy hedges 3× → resume 3× → 3 models) and one
  teacher message could reach dozens of upstream requests.
* **One run, one spare pool.** Whatever layers sit above (Pi retry, Pico
  resume, brain fail-over), the extra requests of one run come out of
  ``RUN_SPARE``. When it is spent, calls still go out — once each, no extras.
* **One hedge**, at the relay's ~p95 first token (25 s). 10-14 live data:
  hedges at 1.5 / 4 / 8 s made 57–72 % of gemini / grok traffic cancelled legs.
* **One retry layer**: only before the first token, only for 429 / 5xx / no
  connection, after a 2 s then 6 s pause (or the relay's ``Retry-After``). A
  dead key or a missing channel switches model instead, at once.
* **Per-key concurrency cap**: requests on one key wait for a slot instead of
  piling onto the relay (``PICO_UPSTREAM_KEY_MAX``).
* **Counters** for ``/health``: requests by purpose and outcome, in-flight and
  peak per key.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections import Counter, OrderedDict
from collections.abc import Awaitable, Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

CALL_BUDGET = 3
RUN_SPARE = 6
HEDGE_S = 25.0
# High effort legitimately holds the first token for tens of seconds.
DEEP_HEDGE_S = 60.0
KEY_MAX_ENV = "PICO_UPSTREAM_KEY_MAX"
_KEY_MAX_DEFAULT = 16
SLOT_WAIT_S = 120.0

HEDGE_FAST_ENV = "PICO_HEDGE_FAST_S"
HEDGE_MEDIUM_ENV = "PICO_HEDGE_MEDIUM_S"
HEDGE_DEEP_ENV = "PICO_HEDGE_DEEP_S"

# Before the first token these are worth one more try (same model).
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529})
# The key behind this model's channel is dead / unpaid: the next model, not a retry.
DEAD_STATUS = frozenset({401, 402, 403})


# Pause before retry n (0-based) inside the call budget: a relay that just said
# 503 / 429 is not better 5 ms later. ``Retry-After`` wins, capped.
RETRY_BACKOFF_S: tuple[float, ...] = (2.0, 6.0)
RETRY_AFTER_MAX_S = 20.0
# What a teacher reads when the relay stayed busy (429 / 5xx) through the budget.
# Not「模型」: teacher text never names the machinery (teacher_text, owner 10-14).
BUSY_TEXT = "Pico 这会儿忙，请稍后再试。"
BUSY_STATUS = frozenset({429, 503, 529})


def verdict(status: int | None) -> str:
    """What to do after an upstream status before any token: retry / switch / stop."""
    if status is None or status in RETRY_STATUS:
        return "retry"  # None = no answer at all (connect / read error)
    if status in DEAD_STATUS:
        return "switch"
    return "stop"


def _chain(exc: BaseException | None):
    seen = 0
    while exc is not None and seen < 5:
        yield exc
        exc = exc.__cause__ or exc.__context__
        seen += 1


def status_of(exc: BaseException) -> int | None:
    """HTTP status the relay answered, wherever it sits in the exception chain."""
    for e in _chain(exc):
        for attr in ("status_code", "status"):
            v = getattr(e, attr, None)
            if isinstance(v, int) and 100 <= v < 600:
                return v
    return None


def no_answer(exc: BaseException) -> bool:
    """Connect / read failure: the relay never answered."""
    for e in _chain(exc):
        if isinstance(e, (TimeoutError, ConnectionError)):
            return True
        if any(c.__name__ in {"HTTPError", "APIConnectionError"} for c in type(e).__mro__):
            return True
    return False


def worth_retry(exc: BaseException) -> bool:
    status = status_of(exc)
    return verdict(status) == "retry" if status is not None else no_answer(exc)


def retry_after(exc: BaseException) -> float | None:
    """Seconds the relay asked us to wait (``Retry-After``), capped; None when it did not say."""
    for e in _chain(exc):
        headers = getattr(e, "headers", None)
        if headers is None:
            headers = getattr(getattr(e, "response", None), "headers", None)
        if not headers:
            continue
        raw = next((v for k, v in dict(headers).items() if k.lower() == "retry-after"), None)
        if raw is None:
            continue
        try:
            secs = float(raw)
        except ValueError:
            try:
                secs = parsedate_to_datetime(raw).timestamp() - time.time()
            except (TypeError, ValueError):
                continue
        return min(max(0.0, secs), RETRY_AFTER_MAX_S)
    return None


def backoff(exc: BaseException, n: int) -> float:
    """Pause before retry ``n`` (0-based) after ``exc``."""
    hint = retry_after(exc)
    if hint is not None:
        return hint
    if not RETRY_BACKOFF_S:
        return 0.0
    return RETRY_BACKOFF_S[min(n, len(RETRY_BACKOFF_S) - 1)]


# --- hedge schedule ----------------------------------------------------------


def _one(raw: str | None, default: float) -> list[float]:
    """At most one hedge. ``off`` / ``0`` turns it off; a list keeps its smallest value."""
    if raw is None or not raw.strip():
        return [default]
    if raw.strip().lower() in {"0", "off", "none"}:
        return []
    vals: list[float] = []
    for part in raw.split(","):
        with suppress(ValueError):
            v = float(part.strip())
            if v > 0:
                vals.append(v)
    return [min(vals)] if vals else [default]


def hedge_after(effort: str | None = None) -> list[float]:
    """Seconds without a first token before the one hedge fires, by reasoning effort."""
    effort = (effort or "").strip().lower()
    if effort in {"high", "xhigh", "max"}:
        return _one(os.environ.get(HEDGE_DEEP_ENV), DEEP_HEDGE_S)
    if effort == "medium":
        return _one(os.environ.get(HEDGE_MEDIUM_ENV), HEDGE_S)
    return _one(os.environ.get(HEDGE_FAST_ENV), HEDGE_S)


# --- per-run spare pool -------------------------------------------------------


@dataclass
class RunState:
    spare: int = RUN_SPARE
    # Pi runs whose fast lane already switches model on a stalled first token:
    # a same-model hedge at the same moment would only be cancelled.
    no_hedge: bool = False
    # Last error status the relay itself answered (the proxy's own 401/403 never land here).
    last_status: int | None = None
    last_error: str = ""
    sent: int = 0


_RUNS: OrderedDict[str, RunState] = OrderedDict()
_RUNS_MAX = 2048


def run_state(run_id: str | None) -> RunState | None:
    if not run_id:
        return None
    st = _RUNS.get(run_id)
    if st is None:
        st = _RUNS[run_id] = RunState()
        while len(_RUNS) > _RUNS_MAX:
            _RUNS.popitem(last=False)
    else:
        _RUNS.move_to_end(run_id)
    return st


def note_upstream_error(run_id: str | None, status: int, text: str) -> None:
    st = run_state(run_id)
    if st is not None:
        st.last_status = status
        st.last_error = (text or "")[:300]


def upstream_error(run_id: str | None) -> str:
    """``upstream <status> <body>`` the relay answered this run, or ''."""
    st = _RUNS.get(run_id or "")
    if st is None or st.last_status is None:
        return ""
    return f"upstream {st.last_status} {st.last_error}".strip()


# --- one logical call ---------------------------------------------------------


@dataclass
class Call:
    """Requests one logical call may still send: the first always, extras from both budgets."""

    purpose: str
    run_id: str | None = None
    budget: int = CALL_BUDGET
    sent: int = 0
    refused: int = field(default=0)

    def can_extra(self) -> bool:
        st = _RUNS.get(self.run_id or "")
        return self.sent < self.budget and (st is None or st.spare > 0)

    def allow(self) -> bool:
        if self.sent == 0:
            self.sent = 1
            st = run_state(self.run_id)
            if st is not None:
                st.sent += 1
            return True
        st = run_state(self.run_id)
        if self.sent >= self.budget or (st is not None and st.spare <= 0):
            self.refused += 1
            count(self.purpose, "budget_spent")
            return False
        self.sent += 1
        if st is not None:
            st.spare -= 1
            st.sent += 1
        return True


async def race[T](
    start: Callable[[int], Awaitable[T] | None],
    call: Call,
    *,
    hedge: Sequence[float] = (),
    relaunch: Callable[[BaseException], bool],
    discard: Callable[[T], Awaitable[None]],
    pause: Callable[[BaseException, int], float] = backoff,
) -> tuple[T, int]:
    """First attempt to succeed wins: ``(result, attempt_index)``.

    ``start(k)`` opens attempt ``k`` (None = no attempt k). It must clean up
    when cancelled. Attempt 1 starts at ``hedge[0]`` s if nothing answered yet,
    or ``pause(exc, n)`` s after an attempt fails and ``relaunch(exc)`` (nothing
    else pending; ``n`` counts retries). Every attempt is
    charged to ``call``; a refused charge means no more attempts. Extra winners
    go to ``discard``. If every attempt fails, the last error is raised.
    """
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    pending: dict[asyncio.Future, int] = {}
    launched = 0
    exhausted = False
    hedged = False
    last_exc: BaseException | None = None
    winner: asyncio.Future | None = None
    winner_idx = 0
    retries = 0

    def launch(why: str = "") -> None:
        nonlocal launched, exhausted
        if exhausted or not call.allow():
            exhausted = True
            return
        aw = start(launched)
        if aw is None:
            exhausted = True
            return
        pending[asyncio.ensure_future(aw)] = launched
        launched += 1
        if why:
            count(call.purpose, why)

    launch()
    try:
        while pending:
            timeout = None
            if not exhausted and not hedged and hedge:
                timeout = max(0.0, t0 + hedge[0] - loop.time())
            done, _ = await asyncio.wait(
                pending, timeout=timeout, return_when=asyncio.FIRST_COMPLETED
            )
            if not done:
                hedged = True
                launch("hedge")
                continue
            failed_retry = False
            for fut in sorted(done, key=lambda f: pending[f]):
                idx = pending.pop(fut)
                exc = fut.exception()
                if exc is None:
                    if winner is None:
                        winner = fut
                        winner_idx = idx
                    else:
                        with suppress(Exception):
                            await discard(fut.result())
                    continue
                last_exc = exc
                failed_retry = failed_retry or relaunch(exc)
            if winner is not None:
                return winner.result(), winner_idx
            if failed_retry and not pending and last_exc is not None:
                wait = pause(last_exc, retries) if call.can_extra() and not exhausted else 0.0
                retries += 1
                if wait > 0:
                    await asyncio.sleep(wait)
                launch("retry")
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("no model attempt was started")
    finally:
        for fut in pending:
            fut.cancel()
        for fut in list(pending):
            with suppress(BaseException):
                res = await fut
                if fut is not winner:
                    with suppress(Exception):
                        await discard(res)


# --- per-key slots and counters ---------------------------------------------


def key_id(key: str) -> str:
    return hashlib.sha256((key or "").encode()).hexdigest()[:8] if key else "nokey"


def key_max() -> int:
    try:
        return max(1, int(os.environ.get(KEY_MAX_ENV) or _KEY_MAX_DEFAULT))
    except ValueError:
        return _KEY_MAX_DEFAULT


_SLOTS: dict[str, asyncio.Semaphore] = {}
_INFLIGHT: Counter[str] = Counter()
_PEAK: Counter[str] = Counter()
_COUNTS: Counter[tuple[str, str]] = Counter()
_STARTED = time.time()


class UpstreamBusy(RuntimeError):
    """Every slot on this key stayed taken for ``SLOT_WAIT_S``."""


def count(purpose: str, outcome: str, n: int = 1) -> None:
    _COUNTS[(purpose, outcome)] += n


async def acquire(key: str, purpose: str) -> Callable[[], None]:
    """Take a slot on ``key`` and count one request; returns the release (call it once)."""
    kid = key_id(key)
    sem = _SLOTS.get(kid)
    if sem is None:
        sem = _SLOTS[kid] = asyncio.Semaphore(key_max())
    try:
        await asyncio.wait_for(sem.acquire(), timeout=SLOT_WAIT_S)
    except TimeoutError:
        count(purpose, "busy")
        raise UpstreamBusy(f"upstream key {kid} busy") from None
    _INFLIGHT[kid] += 1
    _PEAK[kid] = max(_PEAK[kid], _INFLIGHT[kid])
    count(purpose, "sent")
    released = False

    def release() -> None:
        nonlocal released
        if released:
            return
        released = True
        _INFLIGHT[kid] -= 1
        sem.release()

    return release


def count_sync(key: str, purpose: str) -> None:
    """Thread-side calls (rerank) cannot wait on the loop's slots: counted only."""
    count(purpose, "sent")


def stats() -> dict[str, object]:
    by_purpose: dict[str, dict[str, int]] = {}
    for (purpose, outcome), n in sorted(_COUNTS.items()):
        by_purpose.setdefault(purpose, {})[outcome] = n
    return {
        "since": int(_STARTED),
        "key_max": key_max(),
        "calls": by_purpose,
        "inflight": {k: v for k, v in _INFLIGHT.items() if v},
        "peak": dict(_PEAK),
    }


def reset() -> None:
    """Tests: forget slots, counters and runs."""
    global _STARTED
    _SLOTS.clear()
    _INFLIGHT.clear()
    _PEAK.clear()
    _COUNTS.clear()
    _RUNS.clear()
    _STARTED = time.time()
