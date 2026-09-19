const STYLES: Record<string, { label: string; bg: string; fg: string; pulse?: boolean }> = {
  pending: { label: "Pending", bg: "var(--accent-soft)", fg: "var(--accent)" },
  draft: { label: "Draft", bg: "var(--paper-deep)", fg: "var(--muted)" },
  approved: { label: "Approved", bg: "var(--accent-soft)", fg: "var(--accent)" },
  queued: { label: "Queued", bg: "var(--running-soft)", fg: "var(--running)" },
  running: {
    label: "Running",
    bg: "var(--running-soft)",
    fg: "var(--running)",
    pulse: true,
  },
  in_progress: {
    label: "Running",
    bg: "var(--running-soft)",
    fg: "var(--running)",
    pulse: true,
  },
  done: { label: "Done", bg: "var(--ok-soft)", fg: "var(--ok)" },
  completed: { label: "Completed", bg: "var(--ok-soft)", fg: "var(--ok)" },
  completed_with_warnings: {
    label: "Warnings",
    bg: "var(--warn-soft)",
    fg: "var(--warn)",
  },
  failed: { label: "Failed", bg: "var(--danger-soft)", fg: "var(--danger)" },
  skipped: { label: "Skipped", bg: "var(--paper-deep)", fg: "var(--muted)" },
};

export function StatusBadge({ status }: { status: string }) {
  const style = STYLES[status] ?? {
    label: status,
    bg: "var(--paper-deep)",
    fg: "var(--muted)",
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold tracking-wide ${
        style.pulse ? "animate-pulse-soft" : ""
      }`}
      style={{ background: style.bg, color: style.fg }}
    >
      {style.pulse && (
        <span
          className="h-1.5 w-1.5 rounded-full"
          style={{ background: style.fg }}
          aria-hidden
        />
      )}
      {style.label}
    </span>
  );
}
