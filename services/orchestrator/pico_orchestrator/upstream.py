"""The one door to the model relay (pico#1271).

Every request Pico sends to New API goes through here: direct chat
(``provider.stream_chat``), Pi steps through the run proxy (``ws_proxy_router``,
``llm_pass_router``), embeddings / rerank (``meili_kb``) and images
(``image_generate``). The rules live in one place:

* **Budget.** One logical call sends at most ``CALL_BUDGET`` requests, counting
  the first attempt, retries, and model switches together.
* **One run, one spare pool.** In-call retries and immediate Pico resumes
  share ``RUN_SPARE``. When it is spent, calls still go out once each.
  Delayed same-session resumes have their own wait and attempt limits.
* **One retry layer**: only before the first token, only for 429 / 5xx / no
  connection, after a 2 s then 6 s pause (or the relay's ``Retry-After``). A
  dead key or a missing channel switches model instead, at once.
* **Per-key concurrency cap**: requests on one key wait for a slot instead of
  piling onto the relay (``PICO_UPSTREAM_KEY_MAX``), and one teacher's
  requests wait for one of their own slots first (``PICO_UPSTREAM_MEMBER_MAX``).
* **One conversation, one session** (pico#1344): a call made inside
  ``caller_scope`` carries a ``session_id`` that stays the same for the whole
  conversation. AIProxy banned the key when every request looked like a new
  conversation.
* **Counters** for ``/health``: requests by purpose and outcome, in-flight and
  peak per key.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import time
from collections import Counter, OrderedDict
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime

CALL_BUDGET = 3
RUN_SPARE = 6
KEY_MAX_ENV = "PICO_UPSTREAM_KEY_MAX"
# r6 (pico#1450): 20 concurrent users saw LLM p50 of 52 s; no upstream 429s in 24 h.
_KEY_MAX_DEFAULT = 8
MEMBER_MAX_ENV = "PICO_UPSTREAM_MEMBER_MAX"
_MEMBER_MAX_DEFAULT = 2
# Exam handwriting reads (lane pico-ocr) get their own slots: one-shot reads at
# 1–2 s each, 400 a subject; on the shared 2 per teacher a subject took 573 s
# (edu-core#3927, owner 10-26 15:52「AI 阅卷识别太慢，要提高」).
OCR_KEY_MAX_ENV = "PICO_UPSTREAM_OCR_KEY_MAX"
OCR_MEMBER_MAX_ENV = "PICO_UPSTREAM_OCR_MEMBER_MAX"
_OCR_MAX_DEFAULT = 16
# Exam paper reads (exam-answer-extract, purpose "exam") get their own slots too: one paper
# sends 4 pages + 2 stalled-read copies at once, so a background paper parse held all 4 chat
# slots and a teacher's side-rail ask on that same card waited 186 s (edu-core#4095).
# 6 = one paper's whole wave; a second paper queues behind it, never behind chat.
EXAM_KEY_MAX_ENV = "PICO_UPSTREAM_EXAM_KEY_MAX"
_EXAM_MAX_DEFAULT = 6
SLOT_WAIT_S = 120.0

# Before the first token these are worth one more try (same model).
RETRY_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504, 520, 522, 524, 529})
# The key behind this model's channel is dead / unpaid: the next model, not a retry.
DEAD_STATUS = frozenset({401, 402, 403})


# Pause before retry n (0-based) inside the call budget: a relay that just said
# 503 / 429 is not better 5 ms later. ``Retry-After`` wins, capped.
RETRY_BACKOFF_S: tuple[float, ...] = (2.0, 6.0)
RETRY_AFTER_MAX_S = 20.0
# Once Pi has settled after a failed step, leave time for a longer relay outage.
RESUME_BACKOFF_S = (20.0, 60.0, 120.0)
RESUME_WAIT_MAX_S = 300.0
# What a teacher reads when the relay stayed busy (429 / 5xx) through the budget.
# Not「模型」: teacher text never names the machinery (teacher_text, owner 10-14).
BUSY_TEXT = "Pico 这会儿忙，请稍后再试。"
BUSY_STATUS = frozenset({429, 503, 529})


def caller(purpose: str) -> str:
    """``user`` on every request (pico#1271): which Pico road sent it, never who."""
    return f"pico-{purpose}"


def cache_key(instructions: str) -> str | None:
    """Responses ``prompt_cache_key``: calls sharing a system prompt share a cache shard."""
    text = (instructions or "").strip()
    return "pico-" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:16] if text else None


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


def retry_after(exc: BaseException, *, cap: float = RETRY_AFTER_MAX_S) -> float | None:
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
        return min(max(0.0, secs), cap)
    return None


def backoff(exc: BaseException, n: int) -> float:
    """Pause before retry ``n`` (0-based) after ``exc``."""
    hint = retry_after(exc)
    if hint is not None:
        return hint
    if not RETRY_BACKOFF_S:
        return 0.0
    return RETRY_BACKOFF_S[min(n, len(RETRY_BACKOFF_S) - 1)]


# --- per-run spare pool -------------------------------------------------------


@dataclass(frozen=True)
class RelayFailure:
    # None means a transport failure without an HTTP response.
    status: int | None
    text: str
    retry_after_s: float | None


@dataclass
class RunState:
    spare: int = RUN_SPARE
    # Failure of the latest model call, if any (the proxy's own 401/403 never land here).
    relay_failure: RelayFailure | None = None
    sent: int = 0
    # Requests the relay answered 2xx: New API logs each as one call (edu-core#4350).
    answered: int = 0
    # Pi model calls on the loop clock: (reached pico-api, relay's first body chunk) (edu-core#5227).
    llm_calls: list[tuple[float, float]] = field(default_factory=list)
    _llm_inflight: dict[Callable[[], None], float] = field(default_factory=dict)

    @property
    def llm_started_at(self) -> float | None:
        """Earliest send time of a still-open model request, on the loop clock."""
        return min(self._llm_inflight.values(), default=None)

    def track_llm_request(self, release: Callable[[], None]) -> Callable[[], None]:
        """Start at relay dispatch and clear when this request releases its slot."""
        self._llm_inflight[release] = asyncio.get_running_loop().time()

        def done() -> None:
            self._llm_inflight.pop(release, None)
            release()

        return done


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


def note_upstream_error(
    run_id: str | None, status: int | None, text: str, *, retry_after_s: float | None = None
) -> None:
    st = run_state(run_id)
    if st is not None:
        st.relay_failure = RelayFailure(status, text[:300], retry_after_s)


def note_answered(run_id: str | None = None) -> None:
    """One request of this run got a 2xx head (the caller's run when not named)."""
    st = run_state(run_id or CALLER.get().run_id)
    if st is not None:
        st.answered += 1


def note_llm_call(run_id: str | None, arrived: float, first: float) -> None:
    st = run_state(run_id)
    if st is not None:
        st.llm_calls.append((arrived, first))


def llm_calls(run_id: str | None) -> list[tuple[float, float]]:
    st = _RUNS.get(run_id or "")
    return [] if st is None else list(st.llm_calls)


def answered_calls(run_id: str | None) -> int | None:
    """2xx requests this run sent so far; None when this process never saw the run."""
    st = _RUNS.get(run_id or "")
    return None if st is None else st.answered


def upstream_error(run_id: str | None) -> str:
    """``upstream <status> <body>`` the relay answered this run, or ''."""
    st = _RUNS.get(run_id or "")
    failure = st.relay_failure if st is not None else None
    if failure is None or failure.status is None:
        return ""
    return f"upstream {failure.status} {failure.text}".strip()


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
    relaunch: Callable[[BaseException], bool],
    pause: Callable[[BaseException, int], float] = backoff,
) -> tuple[T, int]:
    """Try in sequence and return ``(result, attempt_index)`` on success.

    ``start(k)`` opens attempt ``k`` (None = no attempt k) and cleans up on
    cancellation. After a failure, ``relaunch`` decides whether to try again
    and ``pause`` gives the delay. Every attempt shares the ``call`` budget.
    """
    attempt = 0
    last_exc: Exception | None = None
    while call.allow():
        aw = start(attempt)
        if aw is None:
            break
        if attempt:
            count(call.purpose, "retry")
        try:
            return await aw, attempt
        except Exception as exc:
            if not relaunch(exc):
                raise
            last_exc = exc
            wait = pause(exc, attempt) if call.can_extra() else 0.0
        if wait > 0:
            await asyncio.sleep(wait)
        attempt += 1
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("no model attempt was started")


# --- per-key slots and counters ---------------------------------------------


def key_id(key: str) -> str:
    return hashlib.sha256((key or "").encode()).hexdigest()[:8] if key else "nokey"


def _env_max(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name) or default))
    except ValueError:
        return default


def key_max() -> int:
    return _env_max(KEY_MAX_ENV, _KEY_MAX_DEFAULT)


def member_max() -> int:
    return _env_max(MEMBER_MAX_ENV, _MEMBER_MAX_DEFAULT)


def ocr_key_max() -> int:
    return _env_max(OCR_KEY_MAX_ENV, _OCR_MAX_DEFAULT)


def ocr_member_max() -> int:
    return _env_max(OCR_MEMBER_MAX_ENV, _OCR_MAX_DEFAULT)


def exam_key_max() -> int:
    return _env_max(EXAM_KEY_MAX_ENV, _EXAM_MAX_DEFAULT)


@dataclass(frozen=True)
class Caller:
    """Who a model call is for: ``session`` goes upstream, ``member`` waits for a teacher slot,
    ``run_id`` counts the answered request on that run."""

    session: str = ""
    member: str = ""
    run_id: str = ""


_NOBODY = Caller()
CALLER: ContextVar[Caller] = ContextVar("pico_upstream_caller", default=_NOBODY)


def _h(value: str, *, salt: str) -> str:
    # Same hash as the runner's WorkspaceKey, so a teacher is one member on both roads.
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:32]


# New API logs only the first and last 4 characters of the key: "pcs-" keeps a
# conversation session apart from the old per-prompt "pico-" hash there.
SESSION_PREFIX = "pcs-"


def conversation_session(conversation_id: str) -> str:
    """``session_id`` / ``prompt_cache_key`` for one conversation (≤64 chars, no raw id)."""
    return SESSION_PREFIX + _h(conversation_id, salt="conv")


def member_key(membership_id: str) -> str:
    return _h(membership_id, salt="member") if membership_id else ""


@contextmanager
def caller_scope(*, conversation_id: str | None, run_id: str, membership_id: str = "") -> Iterator[Caller]:
    """Calls made inside carry this conversation's session and wait on this teacher's slots.

    No conversation → the run is its own conversation (same rule as the box workspace).
    """
    who = Caller(
        session=conversation_session(conversation_id or f"run:{run_id}"),
        member=member_key(membership_id),
        run_id=run_id or "",
    )
    token = CALLER.set(who)
    try:
        yield who
    finally:
        CALLER.reset(token)


_SLOTS: dict[str, asyncio.Semaphore] = {}
_MEMBER_SLOTS: dict[str, asyncio.Semaphore] = {}
_OCR_SLOTS: dict[str, asyncio.Semaphore] = {}
_OCR_MEMBER_SLOTS: dict[str, asyncio.Semaphore] = {}
_EXAM_SLOTS: dict[str, asyncio.Semaphore] = {}
_INFLIGHT: Counter[str] = Counter()
_PEAK: Counter[str] = Counter()
_COUNTS: Counter[tuple[str, str]] = Counter()
_STARTED = time.time()


class UpstreamBusy(RuntimeError):
    """Every slot on this key stayed taken for ``SLOT_WAIT_S``."""


def count(purpose: str, outcome: str, n: int = 1) -> None:
    _COUNTS[(purpose, outcome)] += n


async def acquire(key: str, purpose: str, *, ocr: bool = False) -> Callable[[], None]:
    """Take this teacher's slot, then a slot on ``key``, and count one request.

    Returns the release (call it once). The teacher slot comes first so one
    teacher's queue never holds a key slot others could use. ``ocr`` waits on
    the handwriting-read slots instead, so reads and chat never queue on each other;
    purpose ``exam`` (paper reads) waits on its own key slots the same way.
    """
    kid = key_id(key)
    if ocr:
        keys, members, cap = _OCR_SLOTS, _OCR_MEMBER_SLOTS, ocr_key_max
    elif purpose == "exam":
        keys, members, cap = _EXAM_SLOTS, _MEMBER_SLOTS, exam_key_max
    else:
        keys, members, cap = _SLOTS, _MEMBER_SLOTS, key_max
    sem = keys.get(kid)
    if sem is None:
        sem = keys[kid] = asyncio.Semaphore(cap())
    member = CALLER.get().member
    own = None
    if member:
        own = members.get(member)
        if own is None:
            own = members[member] = asyncio.Semaphore(ocr_member_max() if ocr else member_max())
    deadline = time.monotonic() + SLOT_WAIT_S
    try:
        if own is not None:
            await asyncio.wait_for(own.acquire(), timeout=SLOT_WAIT_S)
        try:
            await asyncio.wait_for(sem.acquire(), timeout=max(0.0, deadline - time.monotonic()))
        except BaseException:
            if own is not None:
                own.release()
            raise
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
        if own is not None:
            own.release()

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
        "member_max": member_max(),
        "ocr_key_max": ocr_key_max(),
        "ocr_member_max": ocr_member_max(),
        "exam_key_max": exam_key_max(),
        "calls": by_purpose,
        "inflight": {k: v for k, v in _INFLIGHT.items() if v},
        "peak": dict(_PEAK),
    }


def reset() -> None:
    """Tests: forget slots, counters and runs."""
    global _STARTED
    _SLOTS.clear()
    _MEMBER_SLOTS.clear()
    _OCR_SLOTS.clear()
    _OCR_MEMBER_SLOTS.clear()
    _EXAM_SLOTS.clear()
    _INFLIGHT.clear()
    _PEAK.clear()
    _COUNTS.clear()
    _RUNS.clear()
    _STARTED = time.time()
