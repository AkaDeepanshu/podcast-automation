"use client";

import axios from "axios";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  approveTopic,
  createFocusArea,
  createTopic,
  deleteFocusArea,
  deleteTopic,
  listFocusAreas,
  listTopics,
  runDiscovery,
  runNextTopic,
  updateTopic,
} from "@/lib/api";
import type { FocusArea, TopicItem } from "@/lib/types";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toaster";

function errMsg(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    return typeof detail === "string" ? detail : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}

export default function TopicsPage() {
  const { success, error: toastError, info } = useToast();
  const [topics, setTopics] = useState<TopicItem[]>([]);
  const [areas, setAreas] = useState<FocusArea[]>([]);
  const [loading, setLoading] = useState(true);

  const [title, setTitle] = useState("");
  const [focusId, setFocusId] = useState<number | "">("");
  const [priority, setPriority] = useState(0);
  const [approveOnCreate, setApproveOnCreate] = useState(true);
  const [busy, setBusy] = useState(false);

  const [newArea, setNewArea] = useState("");

  const refresh = useCallback(async () => {
    try {
      const [t, a] = await Promise.all([listTopics(), listFocusAreas()]);
      setTopics(t);
      setAreas(a);
    } catch (e) {
      toastError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [toastError]);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 4000);
    return () => clearInterval(id);
  }, [refresh]);

  async function onAddTopic(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await createTopic({
        title: title.trim(),
        focus_area_id: focusId === "" ? null : focusId,
        priority,
        status: approveOnCreate ? "approved" : "draft",
      });
      setTitle("");
      setPriority(0);
      success("Topic added to the queue.");
      await refresh();
    } catch (e) {
      toastError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRunNext() {
    setBusy(true);
    try {
      const result = await runNextTopic();
      success(`Started “${result.topic}”`);
      await refresh();
    } catch (e) {
      toastError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function onSuggest() {
    setBusy(true);
    try {
      const result = await runDiscovery(3);
      const n = result.created?.length ?? 0;
      if (n === 0) {
        info(
          result.detail
            ? `No topics suggested (${result.detail}).`
            : "No new titles (all duplicates or empty).",
        );
      } else {
        success(`Suggested ${n} topic(s) as ${result.inserted_status ?? "draft"}.`);
      }
      await refresh();
    } catch (e) {
      toastError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function onAddArea(e: FormEvent) {
    e.preventDefault();
    if (!newArea.trim()) return;
    try {
      await createFocusArea(newArea.trim());
      setNewArea("");
      success("Focus area added.");
      await refresh();
    } catch (e) {
      toastError(errMsg(e));
    }
  }

  const approvedCount = topics.filter((t) => t.status === "approved").length;
  const enabledAreas = areas.filter((a) => a.enabled).length;

  return (
    <div className="flex flex-col gap-10">
      <section className="animate-rise flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="font-serif text-2xl tracking-tight text-ink sm:text-[1.75rem]">Topics</h1>
          <p className="mt-1 text-sm text-muted">
            Queue titles for the pipeline. Suggest from focus areas, approve, then
            Run next — or let Automation refill when the queue is low.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={busy || enabledAreas === 0}
            onClick={onSuggest}
            className="rounded-xl border border-line px-5 py-3 text-sm font-semibold transition hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-45"
          >
            Suggest topics
          </button>
          <button
            type="button"
            disabled={busy || approvedCount === 0}
            onClick={onRunNext}
            className="rounded-xl bg-accent px-5 py-3 text-sm font-semibold text-white shadow-[var(--shadow)] transition hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-45"
          >
            Run next ({approvedCount})
          </button>
        </div>
      </section>


      <section className="animate-rise rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
        <h2 className="font-serif text-xl text-ink">Add topic</h2>
        <form onSubmit={onAddTopic} className="mt-5 flex flex-col gap-4">
          <label className="flex flex-col gap-2">
            <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
              Title
            </span>
            <input
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="How to sound more natural in English meetings"
              className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
            />
          </label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Focus area
              </span>
              <select
                value={focusId === "" ? "" : String(focusId)}
                onChange={(e) =>
                  setFocusId(e.target.value ? Number(e.target.value) : "")
                }
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              >
                <option value="">None</option>
                {areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                    {!a.enabled ? " (disabled)" : ""}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Priority
              </span>
              <input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex items-end gap-2 pb-3 text-sm text-ink-soft">
              <input
                type="checkbox"
                checked={approveOnCreate}
                onChange={(e) => setApproveOnCreate(e.target.checked)}
                className="h-4 w-4 accent-[var(--accent)]"
              />
              Approve immediately
            </label>
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={busy || !title.trim()}
              className="rounded-xl bg-accent px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:opacity-50"
            >
              Add to queue
            </button>
          </div>
        </form>
      </section>

      <section className="animate-rise">
        <h2 className="mb-4 font-serif text-xl text-ink">Queue</h2>
        {loading ? (
          <p className="text-sm text-muted">Loading…</p>
        ) : topics.length === 0 ? (
          <div className="rounded-[var(--radius)] border border-dashed border-line bg-surface/70 px-6 py-12 text-center">
            <p className="font-serif text-2xl text-ink">No topics yet</p>
            <p className="mx-auto mt-2 max-w-sm text-sm text-muted">
              Add a title above, approve it, then hit Run next.
            </p>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {topics.map((t, i) => (
              <li
                key={t.id}
                className="animate-rise rounded-[var(--radius)] border border-line bg-surface/90 p-4 shadow-[var(--shadow)] sm:p-5"
                style={{ animationDelay: `${Math.min(i, 8) * 35}ms` }}
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-serif text-lg text-ink">{t.title}</p>
                    <p className="mt-1 text-xs text-muted">
                      {t.focus_area_name ?? "No focus area"} · priority {t.priority} ·{" "}
                      {t.source}
                      {t.job_id ? (
                        <>
                          {" · "}
                          <Link
                            href={`/episodes/${t.job_id}`}
                            className="text-accent hover:text-accent-hover"
                          >
                            {t.job_id}
                          </Link>
                        </>
                      ) : null}
                    </p>
                    {t.error && (
                      <p className="mt-2 text-xs text-[var(--danger)]">{t.error}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={t.status} />
                    {t.status === "draft" && (
                      <button
                        type="button"
                        onClick={async () => {
                          try {
                            await approveTopic(t.id);
                            success("Topic approved.");
                            await refresh();
                          } catch (e) {
                            toastError(errMsg(e));
                          }
                        }}
                        className="rounded-lg border border-line px-3 py-1.5 text-xs font-semibold transition hover:border-accent hover:text-accent"
                      >
                        Approve
                      </button>
                    )}
                    {(t.status === "approved" || t.status === "draft") && (
                      <button
                        type="button"
                        onClick={async () => {
                          await updateTopic(t.id, {
                            priority: t.priority + 1,
                          });
                          await refresh();
                        }}
                        className="rounded-lg px-2 py-1.5 text-xs text-muted hover:text-ink"
                        title="Bump priority"
                      >
                        ↑ Priority
                      </button>
                    )}
                    {!["queued", "running"].includes(t.status) && (
                      <button
                        type="button"
                        onClick={async () => {
                          if (!confirm("Delete this topic?")) return;
                          await deleteTopic(t.id);
                          await refresh();
                        }}
                        className="rounded-lg px-3 py-1.5 text-xs text-muted transition hover:bg-[var(--danger-soft)] hover:text-[var(--danger)]"
                      >
                        Delete
                      </button>
                    )}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="animate-rise rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
        <h2 className="font-serif text-xl text-ink">Focus areas</h2>
        <p className="mt-1 text-sm text-muted">
          Themes used by Suggest topics / Automation refill (e.g. English speaking).
        </p>
        <form onSubmit={onAddArea} className="mt-4 flex gap-3">
          <input
            value={newArea}
            onChange={(e) => setNewArea(e.target.value)}
            placeholder="New focus area"
            className="flex-1 rounded-xl border border-line bg-paper px-4 py-2.5 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            className="rounded-xl border border-line px-4 py-2.5 text-sm font-semibold transition hover:border-accent hover:text-accent"
          >
            Add
          </button>
        </form>
        <ul className="mt-4 flex flex-col gap-2">
          {areas.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between rounded-xl border border-line bg-paper/50 px-4 py-2.5 text-sm"
            >
              <span>
                {a.name}{" "}
                <span className="text-xs text-muted">
                  {a.enabled ? "" : "· disabled"}
                </span>
              </span>
              <button
                type="button"
                onClick={async () => {
                  try {
                    await deleteFocusArea(a.id);
                    await refresh();
                  } catch (e) {
                    toastError(errMsg(e));
                  }
                }}
                className="text-xs text-muted hover:text-[var(--danger)]"
              >
                Delete
              </button>
            </li>
          ))}
          {areas.length === 0 && (
            <li className="text-sm text-muted">No focus areas yet.</li>
          )}
        </ul>
      </section>
    </div>
  );
}
