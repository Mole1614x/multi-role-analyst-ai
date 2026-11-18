from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


def now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Record:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, nullable=False)


class User(Record, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))


class Session(Record, Base):
    __tablename__ = "sessions"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class ResetToken(Record, Base):
    __tablename__ = "reset_tokens"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)


class Workspace(Record, Base):
    __tablename__ = "workspaces"
    name: Mapped[str] = mapped_column(String(100))


class Membership(Record, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id"),)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))


class Project(Record, Base):
    __tablename__ = "projects"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    roles: Mapped[list] = mapped_column(JSON)


class Dataset(Record, Base):
    __tablename__ = "datasets"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(255))


class Version(Record, Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "number"),)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("dataset_versions.id"))
    number: Mapped[int]
    object_key: Mapped[str] = mapped_column(String(160), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    profile: Mapped[dict] = mapped_column(JSON)
    transformations: Mapped[list] = mapped_column(JSON)


class Job(Record, Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_project_status", "project_id", "status"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    requested_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    result: Mapped[dict | None] = mapped_column(JSON(none_as_null=True))
    trace: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text)
    attempt: Mapped[int] = mapped_column(default=0)
    checkpoint_epoch: Mapped[int] = mapped_column(default=0, server_default="0")
    started_at: Mapped[datetime | None] = mapped_column(DateTime)


class Query(Record, Base):
    __tablename__ = "queries"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey("dataset_versions.id"))
    title: Mapped[str] = mapped_column(String(100))
    sql: Mapped[str] = mapped_column(Text)
    result: Mapped[dict] = mapped_column(JSON)


class Dashboard(Record, Base):
    __tablename__ = "dashboards"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    title: Mapped[str] = mapped_column(String(100))
    chart: Mapped[dict] = mapped_column(JSON)


class Artifact(Record, Base):
    __tablename__ = "artifacts"
    __table_args__ = (UniqueConstraint("job_id", "format"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("jobs.id"))
    format: Mapped[str] = mapped_column(String(8))
    object_key: Mapped[str] = mapped_column(String(160), unique=True)


class Audit(Record, Base):
    __tablename__ = "audit_log"
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(100))
    subject: Mapped[str] = mapped_column(String(100))


class Schedule(Record, Base):
    __tablename__ = "schedules"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    payload: Mapped[dict] = mapped_column(JSON)
    interval_minutes: Mapped[int]
    next_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    enabled: Mapped[bool] = mapped_column(default=True)
