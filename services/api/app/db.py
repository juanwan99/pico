"""Pico unique AI ledger — Task / Run / Event / Artifact / ChangeProposal / Workspace."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

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
    inline: Mapped[str] = mapped_column(Text, default="")
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


_engine = None
_Session: async_sessionmaker[AsyncSession] | None = None


def _normalize_url(url: str) -> str:
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path.startswith("./") or not path.startswith("/"):
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("sqlite+aiosqlite:///"):
        if ":///" in url:
            raw = url.split("sqlite+aiosqlite:///")[-1]
            if raw and not raw.startswith(":"):
                Path(raw).parent.mkdir(parents=True, exist_ok=True)
        return url
    return url


def _migrate_sqlite_sync(conn) -> None:
    try:
        rows = conn.execute(text("PRAGMA table_info(tasks)")).fetchall()
    except Exception:
        return
    tcols = {r[1] for r in rows}
    if "conversation_id" not in tcols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN conversation_id VARCHAR(128)"))
    if "workspace_id" not in tcols:
        conn.execute(text("ALTER TABLE tasks ADD COLUMN workspace_id VARCHAR(36)"))


async def init_db() -> None:
    global _engine, _Session
    settings = get_settings()
    url = _normalize_url(settings.pico_database_url)
    _engine = create_async_engine(url, echo=False)
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
) -> EventRow:
    result = await session.execute(
        select(EventRow.seq).where(EventRow.run_id == run_id).order_by(EventRow.seq.desc()).limit(1)
    )
    last = result.scalar_one_or_none()
    seq = (last or 0) + 1
    row = EventRow(
        id=new_id(),
        run_id=run_id,
        seq=seq,
        type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row
