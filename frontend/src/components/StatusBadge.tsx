import { Badge } from "@/components/ui/badge";
import { jobStatusLabel, topicStatusLabel } from "@/lib/labels";
import { cn } from "@/lib/utils";

const TONE: Record<string, string> = {
  pending: "border-transparent bg-[var(--accent-soft)] text-accent",
  draft: "border-transparent bg-paper-deep text-muted-foreground",
  approved: "border-transparent bg-[var(--accent-soft)] text-accent",
  queued: "border-transparent bg-[var(--running-soft)] text-[var(--running)]",
  running: "border-transparent bg-[var(--running-soft)] text-[var(--running)]",
  in_progress:
    "border-transparent bg-[var(--running-soft)] text-[var(--running)]",
  done: "border-transparent bg-[var(--ok-soft)] text-[var(--ok)]",
  completed: "border-transparent bg-[var(--ok-soft)] text-[var(--ok)]",
  completed_with_warnings:
    "border-transparent bg-[var(--warn-soft)] text-[var(--warn)]",
  failed: "border-transparent bg-[var(--danger-soft)] text-[var(--danger)]",
  skipped: "border-transparent bg-paper-deep text-muted-foreground",
};

const TOPIC_STATUSES = new Set([
  "draft",
  "approved",
  "queued",
  "running",
  "done",
  "skipped",
]);

export function StatusBadge({ status }: { status: string }) {
  const pulse = status === "running" || status === "in_progress";
  const label = TOPIC_STATUSES.has(status)
    ? topicStatusLabel(status)
    : jobStatusLabel(status);

  return (
    <Badge
      variant="outline"
      className={cn(
        "gap-1.5 font-semibold tracking-wide",
        TONE[status] ?? "border-transparent bg-paper-deep text-muted-foreground",
        pulse && "animate-pulse-soft",
      )}
    >
      {pulse ? (
        <span
          className="h-1.5 w-1.5 rounded-full bg-current"
          aria-hidden
        />
      ) : null}
      {label}
    </Badge>
  );
}
