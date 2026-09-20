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

export type FocusArea = {
  id: number;
  name: string;
  enabled: boolean;
  created_at: string;
};

export type TopicItem = {
  id: number;
  title: string;
  focus_area_id: number | null;
  focus_area_name: string | null;
  source: string;
  status: string;
  priority: number;
  created_at: string;
  updated_at: string;
  job_id: string | null;
  error: string | null;
  attempt_count: number;
};

export type RunNextResult = {
  topic_id: number;
  job_id: string;
  topic: string;
  task_id: string;
  status: string;
};

export type AutomationSettings = {
  enabled: boolean;
  require_approval: boolean;
  min_queue_depth: number;
  interval_minutes: number;
  timezone: string;
  default_skip_video: boolean;
  last_tick_at: string | null;
  last_run_at: string | null;
  last_run_job_id: string | null;
  last_error: string | null;
  lock_held: boolean;
  approved_queue_depth: number;
};
