"use client";

import axios from "axios";
import Link from "next/link";
import { FormEvent, useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
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
import { topicSourceLabel } from "@/lib/labels";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/layout/EmptyState";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { PageSkeleton } from "@/components/layout/PageSkeleton";
import { SectionCard } from "@/components/layout/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

function errMsg(err: unknown): string {
  if (axios.isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    return typeof detail === "string" ? detail : err.message;
  }
  return err instanceof Error ? err.message : "Something went wrong";
}

export default function TopicsPage() {
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
      toast.error(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, []);

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
      toast.success("Topic added to the queue");
      await refresh();
    } catch (e) {
      toast.error(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function onRunNext() {
    setBusy(true);
    try {
      const result = await runNextTopic();
      toast.success(`Started “${result.topic}”`);
      await refresh();
    } catch (e) {
      toast.error(errMsg(e));
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
        toast.message(
          result.detail
            ? `No topics suggested (${result.detail.replaceAll("_", " ")})`
            : "No new titles available. Existing drafts may already cover these focus areas.",
        );
      } else {
        toast.success(
          `Added ${n} suggested topic${n === 1 ? "" : "s"} as ${result.inserted_status ?? "draft"}`,
        );
      }
      await refresh();
    } catch (e) {
      toast.error(errMsg(e));
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
      toast.success("Focus area added");
      await refresh();
    } catch (e) {
      toast.error(errMsg(e));
    }
  }

  const approvedCount = topics.filter((t) => t.status === "approved").length;
  const enabledAreas = areas.filter((a) => a.enabled).length;

  if (loading) {
    return <PageSkeleton variant="wide" rows={5} />;
  }

  return (
    <PageShell variant="wide">
      <PageHeader
        title="Topics"
        description="Build a queue of episode titles. Suggest from focus areas, approve, then run the next item. Automation can refill the queue when it runs low."
        actions={
          <>
            <Button
              type="button"
              variant="outline"
              size="lg"
              className="rounded-md"
              disabled={busy || enabledAreas === 0}
              onClick={onSuggest}
            >
              Suggest topics
            </Button>
            <Button
              type="button"
              size="lg"
              className="rounded-md"
              disabled={busy || approvedCount === 0}
              onClick={onRunNext}
            >
              Run next ({approvedCount})
            </Button>
          </>
        }
      />

      <SectionCard
        title="Add topic"
        description="Create a title manually, or use Suggest topics after adding focus areas."
      >
        <form onSubmit={onAddTopic} className="flex flex-col gap-4">
          <div className="space-y-2">
            <Label htmlFor="topic-title">Title</Label>
            <Input
              id="topic-title"
              required
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="How to sound more natural in English meetings"
            />
          </div>
          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="focus-area">Focus area</Label>
              <select
                id="focus-area"
                value={focusId === "" ? "" : String(focusId)}
                onChange={(e) =>
                  setFocusId(e.target.value ? Number(e.target.value) : "")
                }
                className="flex h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              >
                <option value="">None</option>
                {areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                    {!a.enabled ? " (disabled)" : ""}
                  </option>
                ))}
              </select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="priority">Priority</Label>
              <Input
                id="priority"
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
              />
            </div>
            <div className="flex items-end pb-1">
              <label className="flex w-full items-center justify-between gap-3 rounded-md border border-line bg-surface px-4 py-2.5 text-sm">
                <span className="text-ink-soft">Approve immediately</span>
                <Switch
                  checked={approveOnCreate}
                  onCheckedChange={setApproveOnCreate}
                />
              </label>
            </div>
          </div>
          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={busy || !title.trim()}
              className="rounded-md"
            >
              Add to queue
            </Button>
          </div>
        </form>
      </SectionCard>

      <section>
        <h2 className="mb-4 font-serif text-xl text-ink">Queue</h2>
        {topics.length === 0 ? (
          <EmptyState
            title="No topics yet"
            description="Add a title above, approve it, then hit Run next."
          />
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
                    <p className="mt-1 text-xs text-muted-foreground">
                      {t.focus_area_name ?? "No focus area"} · priority{" "}
                      {t.priority} · {topicSourceLabel(t.source)}
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
                    {t.error ? (
                      <p className="mt-2 text-xs text-[var(--danger)]">{t.error}</p>
                    ) : null}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge status={t.status} />
                    {t.status === "draft" ? (
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={async () => {
                          try {
                            await approveTopic(t.id);
                            toast.success("Topic approved");
                            await refresh();
                          } catch (e) {
                            toast.error(errMsg(e));
                          }
                        }}
                      >
                        Approve
                      </Button>
                    ) : null}
                    {t.status === "approved" || t.status === "draft" ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={async () => {
                          await updateTopic(t.id, {
                            priority: t.priority + 1,
                          });
                          await refresh();
                        }}
                      >
                        Raise priority
                      </Button>
                    ) : null}
                    {!["queued", "running"].includes(t.status) ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="text-muted-foreground hover:bg-[var(--danger-soft)] hover:text-[var(--danger)]"
                        onClick={async () => {
                          if (!confirm("Delete this topic?")) return;
                          await deleteTopic(t.id);
                          toast.success("Topic deleted");
                          await refresh();
                        }}
                      >
                        Delete
                      </Button>
                    ) : null}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <SectionCard
        title="Focus areas"
        description="Themes used by Suggest topics and Automation refill (for example, English speaking)."
      >
        <form onSubmit={onAddArea} className="flex gap-3">
          <Input
            value={newArea}
            onChange={(e) => setNewArea(e.target.value)}
            placeholder="New focus area"
            className="flex-1"
          />
          <Button type="submit" variant="outline" className="rounded-md">
            Add
          </Button>
        </form>
        <ul className="mt-4 flex flex-col gap-2">
          {areas.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between rounded-md border border-line bg-surface px-4 py-2.5 text-sm"
            >
              <span>
                {a.name}{" "}
                {!a.enabled ? (
                  <span className="text-xs text-muted-foreground">· disabled</span>
                ) : null}
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="text-muted-foreground hover:text-[var(--danger)]"
                onClick={async () => {
                  try {
                    await deleteFocusArea(a.id);
                    await refresh();
                  } catch (e) {
                    toast.error(errMsg(e));
                  }
                }}
              >
                Delete
              </Button>
            </li>
          ))}
          {areas.length === 0 ? (
            <li className="text-sm text-muted-foreground">No focus areas yet.</li>
          ) : null}
        </ul>
      </SectionCard>
    </PageShell>
  );
}
