"use client";

import axios from "axios";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  getAutomation,
  getNotificationStatus,
  runAutomationNow,
  saveAutomation,
  startAutomation,
  stopAutomation,
  testNotification,
} from "@/lib/api";
import type { AutomationSettings } from "@/lib/types";
import { useToast } from "@/components/Toaster";

function errMsg(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    return typeof detail === "string" ? detail : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}

function formatTs(iso: string | null) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default function AutomationPage() {
  const [settings, setSettings] = useState<AutomationSettings | null>(null);
  const [intervalMinutes, setIntervalMinutes] = useState(1440);
  const [minDepth, setMinDepth] = useState(3);
  const [timezone, setTimezone] = useState("UTC");
  const [requireApproval, setRequireApproval] = useState(true);
  const [skipVideo, setSkipVideo] = useState(true);
  const { success, error: toastError } = useToast();
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
      const [s, n] = await Promise.all([
        getAutomation(),
        getNotificationStatus(),
      ]);
      applyLocal(s);
      setTelegramConfigured(n.telegram_configured);
    } catch (e) {
      toastError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [applyLocal, toastError]);

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
      success("Settings saved.");
    } catch (err) {
      toastError(errMsg(err));
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
      success(s.enabled ? "Automation started." : "Automation stopped.");
    } catch (err) {
      toastError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function onRunNow() {
    setBusy(true);
    try {
      const result = await runAutomationNow();
      success(`Started “${result.topic}”`);
      await refresh();
    } catch (err) {
      toastError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  async function onTestTelegram() {
    setBusy(true);
    try {
      await testNotification();
      success("Test Telegram message sent.");
    } catch (err) {
      toastError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  if (loading || !settings) {
    return <p className="animate-rise text-sm text-muted">Loading automation…</p>;
  }

  return (
    <div className="animate-rise mx-auto flex max-w-2xl flex-col gap-8">
      <div>
        <h1 className="font-serif text-2xl text-ink sm:text-[1.75rem]">Automation</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Schedule dequeuing from the Topics queue. Run Celery worker{" "}
          <code className="rounded bg-paper-deep px-1">--concurrency=1</code> plus{" "}
          <code className="rounded bg-paper-deep px-1">celery beat</code>.
        </p>
      </div>


      <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Status
            </p>
            <p className="mt-1 font-serif text-2xl text-ink">
              {settings.enabled ? "Running" : "Stopped"}
            </p>
            <p className="mt-1 text-xs text-muted">
              Lock {settings.lock_held ? "held" : "free"} · {settings.approved_queue_depth}{" "}
              approved in queue
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={busy}
              onClick={onToggle}
              className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              {settings.enabled ? "Stop" : "Start"}
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={onRunNow}
              className="rounded-xl border border-line px-5 py-2.5 text-sm font-semibold transition hover:border-accent hover:text-accent disabled:opacity-50"
            >
              Run now
            </button>
          </div>
        </div>

        <dl className="mt-6 grid gap-3 text-sm sm:grid-cols-2">
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-muted">Last tick</dt>
            <dd className="mt-1 text-ink-soft">{formatTs(settings.last_tick_at)}</dd>
          </div>
          <div>
            <dt className="text-xs uppercase tracking-[0.12em] text-muted">Last run</dt>
            <dd className="mt-1 text-ink-soft">{formatTs(settings.last_run_at)}</dd>
          </div>
          <div className="sm:col-span-2">
            <dt className="text-xs uppercase tracking-[0.12em] text-muted">Last job</dt>
            <dd className="mt-1 font-mono text-xs text-ink-soft">
              {settings.last_run_job_id ? (
                <Link
                  href={`/episodes/${settings.last_run_job_id}`}
                  className="text-accent hover:text-accent-hover"
                >
                  {settings.last_run_job_id}
                </Link>
              ) : (
                "—"
              )}
            </dd>
          </div>
          {settings.last_error && (
            <div className="sm:col-span-2">
              <dt className="text-xs uppercase tracking-[0.12em] text-muted">Last error</dt>
              <dd className="mt-1 text-[var(--danger)]">{settings.last_error}</dd>
            </div>
          )}
        </dl>
      </section>

      <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="font-serif text-xl text-ink">Telegram</h2>
            <p className="mt-1 text-sm text-muted">
              {telegramConfigured
                ? "Bot token and chat ID are set in .env."
                : "Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env."}
            </p>
          </div>
          <button
            type="button"
            disabled={busy || !telegramConfigured}
            onClick={onTestTelegram}
            className="rounded-xl border border-line px-5 py-2.5 text-sm font-semibold transition hover:border-accent hover:text-accent disabled:opacity-50"
          >
            Send test
          </button>
        </div>
      </section>

      <form
        onSubmit={onSave}
        className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6"
      >
        <h2 className="font-serif text-xl text-ink">Schedule</h2>
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Min minutes between runs
            </span>
            <input
              type="number"
              min={1}
              value={intervalMinutes}
              onChange={(e) => setIntervalMinutes(Number(e.target.value))}
              className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
            />
            <span className="text-xs text-muted">1440 ≈ once per day</span>
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Timezone
            </span>
            <input
              value={timezone}
              onChange={(e) => setTimezone(e.target.value)}
              className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Min queue depth (discovery later)
            </span>
            <input
              type="number"
              min={0}
              value={minDepth}
              onChange={(e) => setMinDepth(Number(e.target.value))}
              className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
            />
          </label>
          <div className="flex flex-col justify-end gap-3 pb-1 text-sm">
            <label className="flex items-center gap-2 text-ink-soft">
              <input
                type="checkbox"
                checked={requireApproval}
                onChange={(e) => setRequireApproval(e.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              Require approval for new topics
            </label>
            <label className="flex items-center gap-2 text-ink-soft">
              <input
                type="checkbox"
                checked={skipVideo}
                onChange={(e) => setSkipVideo(e.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              Skip video on automated runs
            </label>
          </div>
        </div>
        <div className="mt-6 flex justify-end">
          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            Save settings
          </button>
        </div>
      </form>

      <p className="text-xs leading-relaxed text-muted">
        Ops:{" "}
        <code className="rounded bg-paper-deep px-1">
          celery -A backend.celery_app worker --concurrency=1 --loglevel=info
        </code>
        {" · "}
        <code className="rounded bg-paper-deep px-1">
          celery -A backend.celery_app beat --loglevel=info
        </code>
      </p>
    </div>
  );
}
