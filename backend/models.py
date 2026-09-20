"""SQLAlchemy ORM models mapped to the existing SQLite schema (+ episode_configs)."""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    topic: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    stages: Mapped[list["Stage"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    tts_lines: Mapped[list["TtsLine"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    episode_config: Mapped["EpisodeConfig | None"] = relationship(
        back_populates="job", uselist=False, cascade="all, delete-orphan"
    )


class Stage(Base):
    __tablename__ = "stages"

    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("jobs.job_id"), primary_key=True
    )
    stage_name: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="stages")


class TtsLine(Base):
    __tablename__ = "tts_lines"

    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("jobs.job_id"), primary_key=True
    )
    line_index: Mapped[int] = mapped_column(Integer, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

    job: Mapped["Job"] = relationship(back_populates="tts_lines")


class EpisodeConfig(Base):
    """Per-job config overrides from the UI (applied in Celery via episode_overrides)."""

    __tablename__ = "episode_configs"

    job_id: Mapped[str] = mapped_column(
        String, ForeignKey("jobs.job_id"), primary_key=True
    )
    target_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    num_segments: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model: Mapped[str | None] = mapped_column(String, nullable=True)
    skip_video: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    job: Mapped["Job"] = relationship(back_populates="episode_config")


class FocusArea(Base):
    __tablename__ = "focus_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)

    topics: Mapped[list["Topic"]] = relationship(back_populates="focus_area")


class Topic(Base):
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    focus_area_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("focus_areas.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual")
    status: Mapped[str] = mapped_column(String, nullable=False, default="draft")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    job_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("jobs.job_id"), nullable=True
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    focus_area: Mapped["FocusArea | None"] = relationship(back_populates="topics")


class AutomationSettings(Base):
    """Singleton row (id=1) for scheduler / automation control."""

    __tablename__ = "automation_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    require_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    min_queue_depth: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    # Minimum minutes between successful starts when Beat is ticking.
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    timezone: Mapped[str] = mapped_column(String, nullable=False, default="UTC")
    default_skip_video: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_tick_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_run_at: Mapped[str | None] = mapped_column(String, nullable=True)
    last_run_job_id: Mapped[str | None] = mapped_column(String, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class ProviderUsage:
    """
    Schema mirror of data/state/provider_usage.db (separate SQLite file).

    Not registered on the jobs Base — the existing ProviderUsageTracker owns
    that DB. Documented here for the API model inventory in the plan.
    """

    __tablename__ = "provider_usage"

