"""Pydantic request/response schemas for the jobs API."""

from pydantic import BaseModel, Field


class EpisodeConfigIn(BaseModel):
    target_duration_minutes: int | None = None
    num_segments: int | None = None
    model: str | None = None


class JobCreate(BaseModel):
    topic: str = Field(..., min_length=1)
    job_id: str | None = None
    skip_video: bool = True
    config: EpisodeConfigIn | None = None


class JobCreated(BaseModel):
    job_id: str
    topic: str
    status: str
    task_id: str


class JobSummary(BaseModel):
    job_id: str
    topic: str
    status: str
    created_at: str
    updated_at: str


class StageOut(BaseModel):
    stage_name: str
    status: str
    error_msg: str | None = None
    updated_at: str


class EpisodeConfigOut(BaseModel):
    target_duration_minutes: int | None = None
    num_segments: int | None = None
    model: str | None = None
    skip_video: bool = True


class JobDetail(JobSummary):
    stages: list[StageOut]
    episode_config: EpisodeConfigOut | None = None


class RetryResponse(BaseModel):
    job_id: str
    from_stage: str
    task_id: str
    status: str


# ---- Topics / focus areas ----

class FocusAreaCreate(BaseModel):
    name: str = Field(..., min_length=1)
    enabled: bool = True


class FocusAreaUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None


class FocusAreaOut(BaseModel):
    id: int
    name: str
    enabled: bool
    created_at: str


class TopicCreate(BaseModel):
    title: str = Field(..., min_length=1)
    focus_area_id: int | None = None
    source: str = "manual"
    status: str = "draft"  # draft | approved (if skipping approval)
    priority: int = 0


class TopicUpdate(BaseModel):
    title: str | None = None
    focus_area_id: int | None = None
    priority: int | None = None
    status: str | None = None


class TopicOut(BaseModel):
    id: int
    title: str
    focus_area_id: int | None
    focus_area_name: str | None = None
    source: str
    status: str
    priority: int
    created_at: str
    updated_at: str
    job_id: str | None
    error: str | None
    attempt_count: int


class RunNextResult(BaseModel):
    topic_id: int
    job_id: str
    topic: str
    task_id: str
    status: str
