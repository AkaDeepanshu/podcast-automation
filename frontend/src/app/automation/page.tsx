"use client";

import axios from "axios";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import {
  getAutomation,
  getNotificationStatus,
  getOpsStatus,
  runAutomationNow,
  saveAutomation,
  startAutomation,
  stopAutomation,
  testNotification,
  type OpsStatus,
} from "@/lib/api";
import type { AutomationSettings } from "@/lib/types";
import { opsCheckLabel } from "@/lib/labels";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { FormSkeleton } from "@/components/layout/PageSkeleton";
import { SectionCard } from "@/components/layout/SectionCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { cn } from "@/lib/utils";

function errMsg(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    return typeof detail === "string" ? detail : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}

function formatTs(iso: string | null) {
  if (!iso) return "Not yet";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

function MetricCard({
  label,
  value,
  detail,
  ok,
}: {
  label: string;
  value: string;
  detail?: string;
  ok: boolean;
}) {
  return (
    <div
      className={cn(
        "rounded-md border p-4",
        ok
          ? "border-line bg-surface"
          : "border-[var(--danger)]/25 bg-[var(--danger-soft)]/40",
      )}
    >
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 font-serif text-xl text-ink">{value}</p>
      {detail ? (
        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  );
}

export default function AutomationPage() {
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [ops, setOps] = useState<OpsStatus | null>(null);
  const [intervalMinutes, setIntervalMinutes] = useState(1440);
  const [minDepth, setMinDepth] = useState(3);
  const [timezone, setTimezone] = useState("UTC");
  const [requireApproval, setRequireApproval] = useState(true);
  const [skipVideo, setSkipVideo] = useState(true);
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const applyLocal = useCallback((s: AutomationSettings) => {
    setSettings(s);
    setIntervalMinutes(s.interval_minutes);
    setMinDepth(s.min_queue_depth);
    setTimezone(s.timezone);
    setRequireApproval(s.require_approval);
    setSkipVideo(s.default_skip_video);
  }, []);

  const refresh = useCallback(async () => {
    try {
      const [s, n, o] = await Promise.all([
        getAutomation(),
        getNotificationStatus(),
        getOpsStatus(),
      ]);
      applyLocal(s);
      setTelegramConfigured(n.telegram_configured);
      setOps(o);
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [applyLocal]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 5000);
    return () => clearInterval(id);
  }, [refresh]);

  async function onSave(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      const s = await saveAutomation({
        interval_minutes: intervalMinutes,
        min_queue_depth: minDepth,
        timezone,
        require_approval: requireApproval,
        default_skip_video: skipVideo,
      });
      applyLocal(s);
      toast.success("Settings saved");
      await refresh();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function onToggle() {
    setBusy(true);
    try {
      const s = settings?.enabled
        ? await stopAutomation()
        : await startAutomation();
      applyLocal(s);
      toast.success(s.enabled ? "Automation started" : "Automation stopped");
      await refresh();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRunNow() {
    setBusy(true);
    try {
      const result = await runAutomationNow();
      toast.success(`Started “${result.topic}”`);
      await refresh();
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function onTestTelegram() {
    setBusy(true);
    try {
      await testNotification();
      toast.success("Test Telegram message sent");
    } catch (err) {
      toast.error(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !settings) {
    return <FormSkeleton />;
  }

  const quota = ops?.gemini_quota;
  const quotaLimit = quota?.daily_limit ?? 0;
  const quotaLabel =
    quota && quotaLimit > 0
      ? `${quota.used_today} of ${quotaLimit} calls today`
      : quota
        ? `${quota.used_today} calls today (no soft limit)`
        : "Unavailable";

  return (
    <PageShell variant="form">
      <PageHeader
        title="Automation"
        description="Run episodes on a schedule from your Topics queue. Keep one Celery worker and Beat process online for unattended production."
      />

      {ops ? (
        <SectionCard
          title="Ops health"
          description="Current status for Redis, workers, Telegram alerts, and Gemini usage."
          action={
            <Badge
              variant="outline"
              className={
                ops.ok
                  ? "border-transparent bg-[var(--ok-soft)] text-[var(--ok)]"
                  : "border-transparent bg-[var(--danger-soft)] text-[var(--danger)]"
              }
            >
              {ops.ok ? "Ready" : "Needs attention"}
            </Badge>
          }
        >
          <div className="grid gap-3 sm:grid-cols-2">
            <MetricCard
              label="Redis"
              value={ops.redis_ok ? "Connected" : "Down"}
              detail={ops.redis_ok ? "Broker is reachable" : "Run docker compose up -d"}
              ok={ops.redis_ok}
            />
            <MetricCard
              label="Worker"
              value={
                ops.workers_online > 0
                  ? `${ops.workers_online} online`
                  : "Offline"
              }
              detail={
                ops.workers_online > 0
                  ? ops.worker_names.join(", ")
                  : "Start Celery with concurrency 1"
              }
              ok={ops.workers_online > 0}
            />
            <MetricCard
              label="Telegram"
              value={ops.telegram_configured ? "Configured" : "Not set"}
              detail={
                ops.telegram_configured
                  ? "Alerts will send from .env credentials"
                  : "Add bot token and chat id to .env"
              }
              ok={ops.telegram_configured}
            />
            <MetricCard
              label="Gemini usage"
              value={quotaLabel}
              detail={
                quota?.near_limit
                  ? `Near the daily limit. Leave about ${quota.headroom_needed} calls free for one episode.`
                  : quota
                    ? `Headroom needed per episode: about ${quota.headroom_needed} calls`
                    : undefined
              }
              ok={!quota?.near_limit}
            />
          </div>

          <div className="mt-5 grid gap-3 rounded-md border border-line bg-surface p-4 sm:grid-cols-3">
            <div>
              <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                Approved topics
              </p>
              <p className="mt-1 font-serif text-lg text-ink">
                {ops.approved_queue_depth}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                Draft + approved
              </p>
              <p className="mt-1 font-serif text-lg text-ink">
                {ops.buffer_queue_depth}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                Minimum depth
              </p>
              <p className="mt-1 font-serif text-lg text-ink">
                {ops.min_queue_depth}
              </p>
            </div>
          </div>

          {ops.in_progress_jobs.length > 0 ? (
            <p className="mt-4 font-mono text-xs text-muted-foreground">
              In progress: {ops.in_progress_jobs.join(", ")}
            </p>
          ) : null}

          {ops.checks.length > 0 ? (
            <ul className="mt-5 space-y-2 border-t border-line pt-4">
              {ops.checks.map((check) => (
                <li key={check} className="text-sm text-ink-soft">
                  <span className="font-medium text-[var(--danger)]">Issue:</span>{" "}
                  {opsCheckLabel(check)}
                </li>
              ))}
              {ops.recommendations.map((rec) => (
                <li key={rec} className="text-sm text-muted-foreground">
                  Suggestion:{" "}
                  {rec.replaceAll("interval_minutes", "run interval")}
                </li>
              ))}
            </ul>
          ) : null}

          <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
            Beat is a separate process. If automation is enabled and “Last tick”
            looks stale, confirm Celery Beat is running.
          </p>
        </SectionCard>
      ) : null}

      <SectionCard title="Scheduler">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
              Status
            </p>
            <p className="mt-1 font-serif text-2xl text-ink">
              {settings.enabled ? "Running" : "Stopped"}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Lock {settings.lock_held ? "held" : "free"} ·{" "}
              {settings.approved_queue_depth} approved in queue
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              disabled={busy}
              onClick={onToggle}
              size="lg"
            >
              {settings.enabled ? "Stop" : "Start"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={busy}
              onClick={onRunNow}
              size="lg"
            >
              Run now
            </Button>
          </div>
        </div>

        <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Last tick
            </dt>
            <dd className="mt-1 text-ink-soft">{formatTs(settings.last_tick_at)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Last run
            </dt>
            <dd className="mt-1 text-ink-soft">{formatTs(settings.last_run_at)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
              Last job
            </dt>
            <dd className="mt-1 font-mono text-xs text-ink-soft">
              {settings.last_run_job_id ? (
                <Link
                  href={`/episodes/${settings.last_run_job_id}`}
                  className="text-accent hover:text-accent-hover"
                >
                  {settings.last_run_job_id}
                </Link>
              ) : (
                "None yet"
              )}
            </dd>
          </div>
          {settings.last_error ? (
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                Last error
              </dt>
              <dd className="mt-1 text-[var(--danger)]">
                {settings.last_error
                  .replaceAll("_", " ")
                  .replace(/^\w/, (c) => c.toUpperCase())}
              </dd>
            </div>
          ) : null}
        </dl>
      </SectionCard>

      <SectionCard
        title="Telegram"
        description={
          telegramConfigured
            ? "Bot token and chat ID are set in .env."
            : "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env."
        }
        action={
          <Button
            type="button"
            variant="outline"
            disabled={busy || !telegramConfigured}
            onClick={onTestTelegram}
          >
            Send test
          </Button>
        }
      >
        <p className="text-sm text-muted-foreground">
          You receive alerts when episodes start or finish, topics are suggested,
          and automation starts or stops.
        </p>
      </SectionCard>

      <SectionCard
        title="Schedule"
        description="For a daily audio episode, use 1440 minutes between runs, keep at least 3 approved topics, and leave skip video enabled."
      >
        <form onSubmit={onSave} className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-2">
            <Label htmlFor="interval">Minutes between runs</Label>
            <Input
              id="interval"
              type="number"
              min={1}
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
            />
            <p className="text-xs text-muted-foreground">
              1440 is roughly once per day. Use a low value such as 5 only for soak tests.
            </p>
          </div>
          <div className="space-y-2">
            <Label htmlFor="tz">Timezone</Label>
            <Input
              id="tz"
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="min-depth">Minimum queue depth</Label>
            <Input
              id="min-depth"
              type="number"
              min={0}
              value={minDepth}
              onChange={(e) => setMinDepth(Number(e.target.value))}
            />
            <p className="text-xs text-muted-foreground">
              Discovery refills when draft plus approved topics fall below this number.
            </p>
          </div>
          <div className="flex flex-col justify-end gap-3 pb-1">
            <label className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3.5 py-2.5 text-sm">
              <span className="text-ink-soft">Require approval for new topics</span>
              <Switch
                checked={requireApproval}
                onCheckedChange={setRequireApproval}
              />
            </label>
            <label className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-3.5 py-2.5 text-sm">
              <span className="text-ink-soft">Skip video on automated runs</span>
              <Switch checked={skipVideo} onCheckedChange={setSkipVideo} />
            </label>
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <Button type="submit" disabled={busy} size="lg">
              Save settings
            </Button>
          </div>
        </form>
      </SectionCard>

      <p className="text-xs leading-relaxed text-muted-foreground">
        CLI check:{" "}
        <code className="rounded bg-paper-deep px-1">python scripts/check_ops.py</code>
      </p>
    </PageShell>
  );
}
