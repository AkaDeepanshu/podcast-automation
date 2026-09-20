/** Human-readable labels for Studio UI (never show raw snake_case to users). */

const JOB_STATUS: Record<string, string> = {
  pending: "Pending",
  in_progress: "In progress",
  completed: "Completed",
  completed_with_warnings: "Completed with warnings",
  failed: "Failed",
};

const TOPIC_STATUS: Record<string, string> = {
  draft: "Draft",
  approved: "Approved",
  queued: "Queued",
  running: "Running",
  done: "Done",
  failed: "Failed",
  skipped: "Skipped",
};

const TOPIC_SOURCE: Record<string, string> = {
  manual: "Manual",
  auto: "Suggested",
  rss: "RSS",
};

const OPS_CHECK: Record<string, string> = {
  redis_down: "Redis is not reachable",
  no_workers: "No Celery worker is online",
  automation_without_worker: "Automation is on but no worker is running",
  telegram_unconfigured: "Telegram alerts are not configured",
  queue_below_min: "Topic queue is below the minimum depth",
  gemini_near_limit: "Gemini daily usage is near the limit",
  job_in_progress: "An episode job is currently in progress",
};

export function jobStatusLabel(status: string): string {
  return JOB_STATUS[status] ?? status.replaceAll("_", " ");
}

export function topicStatusLabel(status: string): string {
  return TOPIC_STATUS[status] ?? status.replaceAll("_", " ");
}

export function topicSourceLabel(source: string): string {
  return TOPIC_SOURCE[source] ?? source.replaceAll("_", " ");
}

export function opsCheckLabel(check: string): string {
  return OPS_CHECK[check] ?? check.replaceAll("_", " ");
}

export function titleCaseWords(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
