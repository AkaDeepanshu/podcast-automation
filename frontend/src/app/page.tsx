"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { deleteJob, listJobs } from "@/lib/api";
import type { JobSummary } from "@/lib/types";
import { NewEpisodeForm } from "@/components/NewEpisodeForm";
import { StatusBadge } from "@/components/StatusBadge";

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
  const [error, setError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const data = await listJobs();
      setJobs(data);
      setError(null);
    } catch {
      setError("Can’t reach the API. Is uvicorn running on port 8000?");
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
    await deleteJob(jobId);
    await refresh();
  }

  return (
    <div>
      <section className="animate-rise mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-3xl tracking-tight text-ink">Episodes</h1>
          <p className="mt-1 text-sm text-muted">
            {loading ? "Loading…" : `${jobs.length} episode${jobs.length === 1 ? "" : "s"}`}
          </p>
        </div>
        <button
          type="button"
          onClick={() => setModalOpen(true)}
          className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-[var(--shadow)] transition hover:bg-accent-hover"
        >
          New episode
        </button>
      </section>

      {error && (
        <div className="mb-6 rounded-[var(--radius)] border border-line bg-[var(--danger-soft)] px-4 py-3 text-sm text-[var(--danger)]">
          {error}
        </div>
      )}

      {!loading && jobs.length === 0 && !error && (
        <div className="animate-rise rounded-[var(--radius)] border border-dashed border-line bg-surface/70 px-6 py-16 text-center">
          <p className="font-serif text-2xl text-ink">No episodes yet</p>
          <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
            Start with a topic. Studio will queue script, voice, and assembly in the background.
          </p>
          <button
            type="button"
            onClick={() => setModalOpen(true)}
            className="mt-6 rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover"
          >
            Create your first episode
          </button>
        </div>
      )}

      <ul className="flex flex-col gap-3">
        {jobs.map((job, index) => (
          <li
            key={job.job_id}
            className="animate-rise group rounded-[var(--radius)] border border-line bg-surface/90 shadow-[var(--shadow)] transition hover:border-accent/30"
            style={{ animationDelay: `${Math.min(index, 8) * 40}ms` }}
          >
            <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between">
              <Link href={`/episodes/${job.job_id}`} className="min-w-0 flex-1">
                <p className="truncate font-serif text-xl text-ink transition group-hover:text-accent">
                  {job.topic}
                </p>
                <p className="mt-1 truncate font-mono text-xs text-muted">{job.job_id}</p>
                <p className="mt-2 text-xs text-muted">{formatDate(job.created_at)}</p>
              </Link>
              <div className="flex items-center gap-3 self-start sm:self-center">
                <StatusBadge status={job.status} />
                <button
                  type="button"
                  onClick={() => onDelete(job.job_id)}
                  className="rounded-lg px-3 py-1.5 text-xs text-muted transition hover:bg-[var(--danger-soft)] hover:text-[var(--danger)]"
                >
                  Delete
                </button>
              </div>
            </div>
          </li>
        ))}
      </ul>

      <NewEpisodeForm
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onCreated={(jobId) => {
          refresh();
          router.push(`/episodes/${jobId}`);
        }}
      />
    </div>
  );
}
