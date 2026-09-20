"use client";

import axios from "axios";
import { FormEvent, useState } from "react";
import { toast } from "sonner";
import { createJob } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";

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

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
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
      toast.success("Episode queued");
      onCreated(created.job_id);
      onClose();
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        toast.error(typeof detail === "string" ? detail : err.message);
      } else {
        toast.error(
          err instanceof Error ? err.message : "Failed to create episode",
        );
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent
        className="sm:max-w-lg"
        showCloseButton
      >
        <DialogHeader>
          <DialogTitle className="font-serif text-2xl text-ink">
            New episode
          </DialogTitle>
          <DialogDescription>
            Topic in, script and audio out. Advanced options are optional.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <div className="space-y-2">
            <Label htmlFor="episode-topic">Topic</Label>
            <Input
              id="episode-topic"
              required
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="Morning habits to improve English"
            />
          </div>

          <div className="flex items-center justify-between gap-3 rounded-md border border-line bg-surface px-4 py-3">
            <div>
              <p className="text-sm font-medium text-ink">Audio only</p>
              <p className="text-xs text-muted-foreground">
                Skip video while iterating (recommended)
              </p>
            </div>
            <Switch
              checked={skipVideo}
              onCheckedChange={setSkipVideo}
            />
          </div>

          <Button
            type="button"
            variant="link"
            className="h-auto self-start px-0"
            onClick={() => setShowAdvanced((v) => !v)}
          >
            {showAdvanced ? "Hide advanced" : "Show advanced"}
          </Button>

          {showAdvanced && (
            <div className="grid gap-4 rounded-md border border-line bg-surface p-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="duration">Duration (minutes)</Label>
                <Input
                  id="duration"
                  type="number"
                  min={5}
                  max={90}
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="segments">Segments</Label>
                <Input
                  id="segments"
                  type="number"
                  min={1}
                  max={12}
                  value={segments}
                  onChange={(e) => setSegments(Number(e.target.value))}
                />
              </div>
              <div className="space-y-2 sm:col-span-2">
                <Label htmlFor="model">Model override (optional)</Label>
                <Input
                  id="model"
                  value={model}
                  onChange={(e) => setModel(e.target.value)}
                  placeholder="e.g. gemini-2.5-flash"
                />
              </div>
            </div>
          )}

          <DialogFooter className="mx-0 mb-0 border-0 bg-transparent p-0">
            <Button type="button" variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={submitting || !topic.trim()}
              size="lg"
            >
              {submitting ? "Starting…" : "Create episode"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
