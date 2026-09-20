"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { deleteJob, listJobs } from "@/lib/api";
import type { JobSummary } from "@/lib/types";
import { NewEpisodeForm } from "@/components/NewEpisodeForm";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PageSkeleton } from "@/components/layout/PageSkeleton";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function formatDate(iso: string) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function DashboardPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data);
    } catch {
      toast.error("Unable to reach the API. Confirm the server is running on port 8000.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  async function onDelete(jobId: string) {
    if (!confirm(`Delete episode “${jobId}”? This removes outputs too.`)) return;
    try {
      await deleteJob(jobId);
      toast.success("Episode deleted");
      await refresh();
    } catch {
      toast.error("Failed to delete episode");
    }
  }

  if (loading) {
    return <PageSkeleton variant="wide" rows={4} />;
  }

  return (
    <PageShell variant="wide">
      <PageHeader
        title="Episodes"
        description={
          jobs.length === 0
            ? "Create and track podcast episodes from topic through finished audio."
            : jobs.length === 1
              ? "1 episode in your library"
              : `${jobs.length} episodes in your library`
        }
        actions={
          <Button
            size="lg"
            className="rounded-md"
            onClick={() => setModalOpen(true)}
          >
            New episode
          </Button>
        }
      />

      {jobs.length === 0 ? (
        <EmptyState
          title="No episodes yet"
          description="Create an episode from a topic. Studio will run script, voice, and assembly in the background."
          action={
            <Button
              size="lg"
              className="rounded-md"
              onClick={() => setModalOpen(true)}
            >
              Create your first episode
            </Button>
          }
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {jobs.map((job, index) => (
            <li
              key={job.job_id}
              className="animate-rise"
              style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
            >
              <Card className="group border-line bg-surface/90 p-0 shadow-[var(--shadow)] transition hover:border-accent/30">
                <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
                  <Link
                    href={`/episodes/${job.job_id}`}
                    className="min-w-0 flex-1"
                  >
                    <p className="truncate font-serif text-xl text-ink transition group-hover:text-accent">
                      {job.topic}
                    </p>
                    <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
                      {job.job_id}
                    </p>
                    <p className="mt-2 text-xs text-muted-foreground">
                      {formatDate(job.created_at)}
                    </p>
                  </Link>
                  <div className="flex items-center gap-3 self-start sm:self-center">
                    <StatusBadge status={job.status} />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="text-muted-foreground hover:bg-[var(--danger-soft)] hover:text-[var(--danger)]"
                      onClick={() => onDelete(job.job_id)}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <NewEpisodeForm
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(jobId) => {
          refresh();
          router.push(`/episodes/${jobId}`);
        }}
      />
    </PageShell>
  );
}
