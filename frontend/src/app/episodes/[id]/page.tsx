"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { getJob, retryJob } from "@/lib/api";
import type { JobDetail } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { StageTracker } from "@/components/StageTracker";
import { LogStream } from "@/components/LogStream";
import { MediaPlayer } from "@/components/MediaPlayer";

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function stageDone(job: JobDetail, name: string) {
  return job.stages.some((s) => s.stage_name === name && s.status === "completed");
}

export default function EpisodeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [job, setJob] = useState<JobDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryingStage, setRetryingStage] = useState<string | null>(null);
  const [retryError, setRetryError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await getJob(id);
      setJob(data);
      setError(null);
    } catch {
      setError("Episode not found or API unreachable.");
    }
  }, [id]);

  useEffect(() => {
    refresh();
    const timer = setInterval(refresh, 4000);
    return () => clearInterval(timer);
  }, [refresh]);

  const hasScript = useMemo(
    () => (job ? stageDone(job, "script") : false),
    [job],
  );
  const hasAudio = useMemo(
    () => (job ? stageDone(job, "assembly") : false),
    [job],
  );
  const hasVideo = useMemo(
    () => (job ? stageDone(job, "video") : false),
    [job],
  );

  async function onRetry(fromStage: string) {
    setRetryError(null);
    setRetryingStage(fromStage);
    try {
      await retryJob(id, fromStage);
      await refresh();
    } catch (err) {
      setRetryError(
        err instanceof Error ? err.message : "Retry failed",
      );
    } finally {
      setRetryingStage(null);
    }
  }

  if (error && !job) {
    return (
      <div className="animate-rise">
        <Link href="/" className="text-sm text-accent hover:text-accent-hover">
          ← Episodes
        </Link>
        <p className="mt-6 rounded-[var(--radius)] bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </p>
      </div>
    );
  }

  if (!job) {
    return (
      <div className="animate-rise text-sm text-muted">Loading episode…</div>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="animate-rise">
        <Link
          href="/"
          className="text-sm font-medium text-accent transition hover:text-accent-hover"
        >
          ← Episodes
        </Link>
        <div className="mt-4 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent">
              Episode
            </p>
            <h1 className="font-serif text-3xl tracking-tight text-ink sm:text-4xl">
              {job.topic}
            </h1>
            <p className="mt-2 truncate font-mono text-xs text-muted">
              {job.job_id}
            </p>
            <p className="mt-2 text-xs text-muted">
              Created {formatDate(job.created_at)}
            </p>
          </div>
          <StatusBadge status={job.status} />
        </div>
        {retryError && (
          <p className="mt-4 rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]">
            {retryError}
          </p>
        )}
      </div>

      <div className="animate-rise" style={{ animationDelay: "40ms" }}>
        <StageTracker
          stages={job.stages}
          onRetry={onRetry}
          retryingStage={retryingStage}
        />
      </div>

      <div
        className="animate-rise grid gap-6 lg:grid-cols-2"
        style={{ animationDelay: "80ms" }}
      >
        <LogStream jobId={job.job_id} />
        <MediaPlayer
          jobId={job.job_id}
          hasScript={hasScript}
          hasAudio={hasAudio}
          hasVideo={hasVideo}
        />
      </div>
    </div>
  );
}
