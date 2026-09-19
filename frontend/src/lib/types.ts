export type JobSummary = {
  job_id: string;
  topic: string;
  status: string;
  created_at: string;
  updated_at: string;
};

export type StageOut = {
  stage_name: string;
  status: string;
  error_msg: string | null;
  updated_at: string;
};

export type EpisodeConfigOut = {
  target_duration_minutes: number | null;
  num_segments: number | null;
  model: string | null;
  skip_video: boolean;
};

export type JobDetail = JobSummary & {
  stages: StageOut[];
  episode_config: EpisodeConfigOut | null;
};

export type JobCreatePayload = {
  topic: string;
  job_id?: string;
  skip_video?: boolean;
  config?: {
    target_duration_minutes?: number;
    num_segments?: number;
    model?: string;
  };
};

export type JobCreated = {
  job_id: string;
  topic: string;
  status: string;
  task_id: string;
};
