"use client";

import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PageSkeleton } from "@/components/layout/PageSkeleton";
import { SectionCard } from "@/components/layout/SectionCard";
import { StatusBadge } from "@/components/StatusBadge";
import { StageTracker } from "@/components/StageTracker";
import { LogStream } from "@/components/LogStream";
import { MediaPlayer } from "@/components/MediaPlayer";
import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { getJob, retryJob } from "@/lib/api";
import type { JobDetail } from "@/lib/types";
import { titleCaseWords } from "@/lib/labels";

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
    setRetryingStage(fromStage);
    try {
      await retryJob(id, fromStage);
      toast.success(`Retrying from ${titleCaseWords(fromStage)}`);
      await refresh();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Retry failed");
    } finally {
      setRetryingStage(null);
    }
  }

  if (error && !job) {
    return (
      <PageShell variant="wide">
        <EmptyState
          title="Episode not found"
          description={error}
          action={
            <Link
              href="/"
              className="inline-flex h-9 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground transition hover:bg-primary/80"
            >
              Back to episodes
            </Link>
          }
        />
      </PageShell>
    );
  }

  if (!job) {
    return <PageSkeleton variant="wide" rows={4} />;
  }

  return (
    <PageShell variant="wide">
      <div>
        <Link
          href="/"
          className="text-sm font-medium text-accent transition hover:text-accent-hover"
        >
          ← Episodes
        </Link>
        <PageHeader
          className="mt-4"
          title={job.topic}
          description={`Created ${formatDate(job.created_at)} · ${job.job_id}`}
          actions={<StatusBadge status={job.status} />}
        />
      </div>

      <SectionCard title="Pipeline stages">
        <StageTracker
          stages={job.stages}
          onRetry={onRetry}
          retryingStage={retryingStage}
        />
      </SectionCard>

      <div className="grid gap-6 lg:grid-cols-2">
        <SectionCard title="Live logs">
          <LogStream jobId={job.job_id} />
        </SectionCard>
        <SectionCard title="Media">
          <MediaPlayer
            jobId={job.job_id}
            hasScript={hasScript}
            hasAudio={hasAudio}
            hasVideo={hasVideo}
          />
        </SectionCard>
      </div>
    </PageShell>
  );
}
