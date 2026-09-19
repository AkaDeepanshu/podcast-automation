"use client";

import axios from "axios";
import { FormEvent, useState } from "react";
import { createJob } from "@/lib/api";

type Props = {
  open: boolean;
  onClose: () => void;
  onCreated: (jobId: string) => void;
};

export function NewEpisodeForm({ open, onClose, onCreated }: Props) {
  const [topic, setTopic] = useState("");
  const [skipVideo, setSkipVideo] = useState(true);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [duration, setDuration] = useState(30);
  const [segments, setSegments] = useState(6);
  const [model, setModel] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const created = await createJob({
        topic: topic.trim(),
        skip_video: skipVideo,
        config: {
          target_duration_minutes: duration,
          num_segments: segments,
          model: model.trim() || undefined,
        },
      });
      setTopic("");
      onCreated(created.job_id);
      onClose();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        setError(typeof detail === "string" ? detail : err.message);
      } else {
        setError(err instanceof Error ? err.message : "Failed to create episode");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div
      className="animate-backdrop fixed inset-0 z-50 flex items-end justify-center bg-[rgba(22,27,24,0.45)] p-4 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      role="presentation"
    >
      <div
        className="animate-rise w-full max-w-lg rounded-[var(--radius)] border border-line bg-surface p-6 shadow-[var(--shadow)] sm:p-8"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="new-episode-title"
      >
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <h2 id="new-episode-title" className="font-serif text-2xl text-ink">
              New episode
            </h2>
            <p className="mt-1 text-sm text-muted">
              Topic in, script and audio out. Advanced options are optional.
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-muted transition-colors hover:text-ink"
          >
            Close
          </button>
        </div>

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <label className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Topic
            </span>
            <input
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Morning habits to improve English"
              className="rounded-xl border border-line bg-paper px-4 py-3 text-base text-ink outline-none transition focus:border-accent"
            />
          </label>

          <label className="flex cursor-pointer items-center gap-3 text-sm text-ink-soft">
            <input
              type="checkbox"
              checked={skipVideo}
              onChange={(e) => setSkipVideo(e.target.checked)}
              className="h-4 w-4 accent-[var(--accent)]"
            />
            Skip video (audio only — recommended while iterating)
          </label>

          <button
            type="button"
            onClick={() => setShowAdvanced((v) => !v)}
            className="self-start text-sm font-medium text-accent transition-colors hover:text-accent-hover"
          >
            {showAdvanced ? "Hide advanced" : "Advanced"}
          </button>

          {showAdvanced && (
            <div className="grid gap-4 rounded-xl border border-line bg-paper/60 p-4 sm:grid-cols-2">
              <label className="flex flex-col gap-2 text-sm">
                <span className="text-muted">Duration (minutes)</span>
                <input
                  type="number"
                  min={5}
                  max={90}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="rounded-lg border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm">
                <span className="text-muted">Segments</span>
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={segments}
                  onChange={(e) => setSegments(Number(e.target.value))}
                  className="rounded-lg border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                />
              </label>
              <label className="flex flex-col gap-2 text-sm sm:col-span-2">
                <span className="text-muted">Model override (optional)</span>
                <input
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. gemini-2.5-flash"
                  className="rounded-lg border border-line bg-surface px-3 py-2 outline-none focus:border-accent"
                />
              </label>
            </div>
          )}

          {error && (
            <p className="rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-sm text-[var(--danger)]">
              {error}
            </p>
          )}

          <div className="mt-2 flex items-center justify-end gap-3">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl px-4 py-2.5 text-sm text-muted transition hover:text-ink"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !topic.trim()}
              className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {submitting ? "Starting…" : "Create episode"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
