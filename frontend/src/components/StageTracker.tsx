"use client";

import type { StageOut } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";

const STAGE_ORDER = ["script", "tts", "assembly", "video"] as const;

const LABELS: Record<string, string> = {
  script: "Script",
  tts: "Voice",
  assembly: "Assembly",
  video: "Video",
};

type Props = {
  stages: StageOut[];
  onRetry: (fromStage: string) => void;
  retryingStage: string | null;
};

export function StageTracker({ stages, onRetry, retryingStage }: Props) {
  const byName = Object.fromEntries(stages.map((s) => [s.stage_name, s]));

  return (
    <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
      <h2 className="mb-5 font-serif text-xl text-ink">Pipeline</h2>
      <ol className="flex flex-col gap-0 sm:flex-row sm:items-stretch sm:gap-0">
        {STAGE_ORDER.map((name, index) => {
          const stage = byName[name];
          const status = stage?.status ?? "pending";
          const failed = status === "failed";

          return (
            <li
              key={name}
              className="relative flex flex-1 flex-col gap-3 border-b border-line py-4 last:border-b-0 sm:border-b-0 sm:border-r sm:px-4 sm:py-0 sm:last:border-r-0 sm:first:pl-0 sm:last:pr-0"
            >
              <div className="flex items-center justify-between gap-2 sm:flex-col sm:items-start sm:gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
                    {String(index + 1).padStart(2, "0")}
                  </p>
                  <p className="mt-1 font-serif text-lg text-ink">{LABELS[name]}</p>
                </div>
                <StatusBadge status={status} />
              </div>

              {stage?.error_msg && (
                <p className="rounded-lg bg-[var(--danger-soft)] px-3 py-2 text-xs leading-relaxed text-[var(--danger)]">
                  {stage.error_msg}
                </p>
              )}

              {(failed || status === "in_progress") && (
                <button
                  type="button"
                  disabled={retryingStage !== null || status === "in_progress"}
                  onClick={() => onRetry(name)}
                  className="self-start rounded-lg border border-line px-3 py-1.5 text-xs font-semibold text-ink-soft transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {retryingStage === name
                    ? "Retrying…"
                    : failed
                      ? "Retry this stage"
                      : "Running…"}
                </button>
              )}

              {status === "completed" && (
                <button
                  type="button"
                  disabled={retryingStage !== null}
                  onClick={() => onRetry(name)}
                  className="self-start text-xs font-medium text-muted transition hover:text-accent disabled:opacity-40"
                >
                  Re-run from here
                </button>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
