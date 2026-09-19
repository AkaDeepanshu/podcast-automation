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
