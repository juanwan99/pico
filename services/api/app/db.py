"""Pico unique AI ledger — Task / Run / Event / Artifact / ChangeProposal / Workspace."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    event,
    select,
    text,
)
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.pool import NullPool

from app.settings import get_settings


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def new_id() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class WorkspaceRow(Base):
    """Managed execution boundary (browser-safe; not local full-disk)."""

    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    kind: Mapped[str] = mapped_column(String(32), default="managed")
    note: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    conversation_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)

    runs: Mapped[list[RunRow]] = relationship(back_populates="task", cascade="all, delete-orphan")
    artifacts: Mapped[list[ArtifactRow]] = relationship(
        back_populates="task", cascade="all, delete-orphan"
    )


class RunRow(Base):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage_json: Mapped[str] = mapped_column(Text, default="{}")
    cancel_requested: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    task: Mapped[TaskRow] = relationship(back_populates="runs")
    events: Mapped[list[EventRow]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="EventRow.seq"
    )


class EventRow(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_events_run_id_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("runs.id"), index=True)
    seq: Mapped[int] = mapped_column(Integer, index=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    run: Mapped[RunRow] = relationship(back_populates="events")

    @property
    def payload(self) -> dict[str, Any]:
        try:
            return json.loads(self.payload_json or "{}")
        except json.JSONDecodeError:
            return {}


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(64), default="doc")
    title: Mapped[str] = mapped_column(String(512), default="")
    # Payload storage: utf8 text OR base64(binary). Never force binary through UTF-8.
    inline: Mapped[str] = mapped_column(Text, default="")
    content_encoding: Mapped[str] = mapped_column(String(16), default="utf8")
    content_sha256: Mapped[str] = mapped_column(String(64), default="")
    byte_size: Mapped[int] = mapped_column(Integer, default=0)
    folder_id: Mapped[str] = mapped_column(String(36), default="", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    task: Mapped[TaskRow] = relationship(back_populates="artifacts")


class ChangeProposalRow(Base):
    """S7 minimal human-confirm path — no silent business write."""

    __tablename__ = "change_proposals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128))
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
    status: Mapped[str] = mapped_column(String(32), default="proposed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    confirmed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    audit_json: Mapped[str] = mapped_column(Text, default="[]")


class AutomationRow(Base):
    """Scheduled trigger config (browser product; server-side runner)."""

    __tablename__ = "automations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(256), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    schedule_kind: Mapped[str] = mapped_column(String(32), default="periodic")  # periodic|interval|once
    schedule_json: Mapped[str] = mapped_column(Text, default="{}")
    workspace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enabled: Mapped[int] = mapped_column(Integer, default=1)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(64))
    subject_type: Mapped[str] = mapped_column(String(64), default="")
    subject_id: Mapped[str] = mapped_column(String(64), default="")
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class UsageEventRow(Base):
    """Product usage meter — statistics/management only. No price/currency/billing."""

    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_usage_events_idempotency"),
        Index("ix_usage_events_tenant_created", "school_id", "membership_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_unknown: Mapped[int] = mapped_column(Integer, default=0)
    estimated: Mapped[int] = mapped_column(Integer, default=0)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    extra_json: Mapped[str] = mapped_column(Text, default="{}")
    idempotency_key: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, index=True)


class EduSsoJtiRow(Base):
    """One-time edu web SSO tickets. jti is consumed on first successful use."""

    __tablename__ = "edu_sso_jti"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    school_id: Mapped[str] = mapped_column(String(128), default="")
    membership_id: Mapped[str] = mapped_column(String(128), default="")
    exp: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class EduNamedBindRow(Base):
    """Named school item ids for this membership / conversation. Ids only, no bodies."""

    __tablename__ = "edu_named_bind"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "membership_id",
            "conversation_id",
            name="edu_named_bind_convo_uniq",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    conversation_id: Mapped[str] = mapped_column(String(128), default="")
    item_ids_json: Mapped[str] = mapped_column(Text, default="[]")
    field_id: Mapped[str] = mapped_column(String(36), default="")
    archive_folder_id: Mapped[str] = mapped_column(String(36), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class PersonalFolderRow(Base):
    """Membership folders inside 「我的文件」. Not a school library."""

    __tablename__ = "personal_folders"
    __table_args__ = (
        UniqueConstraint(
            "school_id",
            "membership_id",
            "name",
            name="personal_folders_name_uniq",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    school_id: Mapped[str] = mapped_column(String(128), index=True)
    membership_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(40), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None


def _sqlite_base_dir() -> Path:
    """Stable base for relative sqlite paths (never follow process cwd).

    Concurrent agent work may chdir into workspaces; resolving `./data/pico.db`
    against Path.cwd() caused intermittent "unable to open database file".
    Prefer /app (container), else nearest repo/package root with data|services.
    """
    app_root = Path("/app")
    if app_root.is_dir():
        return app_root
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "data").is_dir() or (parent / "services").is_dir():
            return parent
    return Path.cwd()


def _normalize_url(url: str) -> str:
    def _abs_sqlite_file(raw: str) -> str:
        if not raw or raw.startswith(":"):
            return raw
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = (_sqlite_base_dir() / path).resolve()
        else:
            path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path.as_posix()

    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path and not path.startswith(":"):
            path = _abs_sqlite_file(path)
            return f"sqlite+aiosqlite:///{path}"
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("sqlite+aiosqlite:///"):
        raw = url.split("sqlite+aiosqlite:///", 1)[-1]
        # strip query if any
        file_part = raw.split("?", 1)[0]
        if file_part and not file_part.startswith(":"):
            abs_path = _abs_sqlite_file(file_part)
            suffix = raw[len(file_part) :]
            return f"sqlite+aiosqlite:///{abs_path}{suffix}"
        return url
    return url


def _migrate_sqlite_sync(conn) -> None:
    try:
        rows = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
    except Exception:  # noqa: BLE001
        return
    tcols = {r[1] for r in rows}
    if "conversation_id" not in tcols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN conversation_id VARCHAR(128)"))
    if "workspace_id" not in tcols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN workspace_id VARCHAR(36)"))

    try:
        art_rows = conn.execute(text("PRAGMA table_info(artifacts)")).fetchall()
    except Exception:  # noqa: BLE001
        art_rows = []
    acols = {r[1] for r in art_rows}
    if acols:
        if "content_encoding" not in acols:
            conn.execute(
                text(
                    "ALTER TABLE artifacts ADD COLUMN content_encoding VARCHAR(16) DEFAULT 'utf8'"
                )
            )
        if "content_sha256" not in acols:
            conn.execute(
                text("ALTER TABLE artifacts ADD COLUMN content_sha256 VARCHAR(64) DEFAULT ''")
            )
        if "byte_size" not in acols:
            conn.execute(text("ALTER TABLE artifacts ADD COLUMN byte_size INTEGER DEFAULT 0"))
        if "folder_id" not in acols:
            conn.execute(text("ALTER TABLE artifacts ADD COLUMN folder_id VARCHAR(36) DEFAULT ''"))

    try:
        named_rows = conn.execute(text("PRAGMA table_info(edu_named_bind)")).fetchall()
    except Exception:  # noqa: BLE001
        named_rows = []
    ncols = {r[1] for r in named_rows}
    if ncols and "field_id" not in ncols:
        conn.execute(text("ALTER TABLE edu_named_bind ADD COLUMN field_id VARCHAR(36) DEFAULT ''"))
    if ncols and "archive_folder_id" not in ncols:
        conn.execute(
            text("ALTER TABLE edu_named_bind ADD COLUMN archive_folder_id VARCHAR(36) DEFAULT ''")
        )

    duplicate_runs = conn.execute(
        text("SELECT run_id FROM events GROUP BY run_id, seq HAVING COUNT(*) > 1")
    ).scalars()
    for run_id in set(duplicate_runs):
        event_ids = conn.execute(
            text(
                "SELECT id FROM events WHERE run_id = :run_id "
                "ORDER BY seq, created_at, id"
            ),
            {"run_id": run_id},
        ).scalars()
        for seq, event_id in enumerate(event_ids, start=1):
            conn.execute(
                text("UPDATE events SET seq = :seq WHERE id = :event_id"),
                {"seq": seq, "event_id": event_id},
            )
    conn.execute(
        text("CREATE UNIQUE INDEX IF NOT EXISTS uq_events_run_id_seq ON events (run_id, seq)")
    )


def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    # Concurrent cancel + emit under aiosqlite needs WAL + longer wait (prod #165 lock).
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=60000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


async def init_db() -> None:
    global _engine, _Session
    settings = get_settings()
    url = _normalize_url(settings.pico_database_url)
    engine_kwargs: dict[str, Any] = {"echo": False}
    if "sqlite" in url:
        # aiosqlite + default QueuePool can surface "unable to open database file"
        # under overlapping runs/cancel (stage #256 concurrent window).
        # NullPool: one connection per checkout; WAL + busy_timeout handle locks.
        engine_kwargs["poolclass"] = NullPool
        engine_kwargs["connect_args"] = {
            "timeout": 30.0,
            "check_same_thread": False,
        }
    _engine = create_async_engine(url, **engine_kwargs)
    if "sqlite" in url:
        event.listen(_engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    _Session = async_sessionmaker(_engine, expire_on_commit=False)
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        if "sqlite" in url:
            await conn.run_sync(_migrate_sqlite_sync)


async def get_session() -> AsyncIterator[AsyncSession]:
    if _Session is None:
        await init_db()
    assert _Session is not None
    async with _Session() as session:
        yield session


def session_factory() -> async_sessionmaker[AsyncSession]:
    if _Session is None:
        raise RuntimeError("DB not initialized — call init_db() first")
    return _Session


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    commit: bool = True,
) -> EventRow:
    last_err: Exception | None = None
    for attempt in range(5):
        try:
            async with session.begin_nested():
                result = await session.execute(
                    select(EventRow.seq)
                    .where(EventRow.run_id == run_id)
                    .order_by(EventRow.seq.desc())
                    .limit(1)
                )
                last = result.scalar_one_or_none()
                row = EventRow(
                    id=new_id(),
                    run_id=run_id,
                    seq=(last or 0) + 1,
                    type=event_type,
                    payload_json=json.dumps(payload, ensure_ascii=False),
                )
                session.add(row)
                await session.flush()
            if commit:
                await session.commit()
            await session.refresh(row)
            return row
        except IntegrityError as exc:
            last_err = exc
            if attempt >= 4:
                raise
            await session.rollback()
        except OperationalError as exc:
            last_err = exc
            # sqlite locked / unable to open under concurrent cancel/emit
            if attempt >= 4:
                raise
            await session.rollback()
            await asyncio.sleep(0.05 * (attempt + 1))
    raise RuntimeError(f"event sequence allocation exhausted: {last_err!r}")
