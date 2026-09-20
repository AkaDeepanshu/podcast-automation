"use client";

import axios from "axios";
import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  assetUrl,
  getAppConfig,
  saveAppConfig,
  uploadAsset,
  type AppConfigResponse,
} from "@/lib/api";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/PageHeader";
import { PageShell } from "@/components/layout/PageShell";
import { FormSkeleton } from "@/components/layout/PageSkeleton";
import { SectionCard } from "@/components/layout/SectionCard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

type FormState = {
  scriptGenerator: string;
  geminiModel: string;
  groqModel: string;
  duration: number;
  segments: number;
  pauseTurns: number;
  pauseSegments: number;
  forbidden: string;
  speakerAName: string;
  speakerAVoice: string;
  speakerBName: string;
  speakerBVoice: string;
};

const GENERATOR_OPTIONS = [
  { value: "fallback_chain", label: "Fallback chain (Gemini → Lite → Groq)" },
  { value: "gemini", label: "Gemini only" },
  { value: "groq", label: "Groq only" },
];

function toForm(data: AppConfigResponse): FormState {
  const cfg = data.config;
  const sg = (cfg.script_generation ?? {}) as Record<string, unknown>;
  const providers = (cfg.providers ?? {}) as Record<string, unknown>;
  const tts = (cfg.tts ?? {}) as Record<string, unknown>;
  const gemini = (sg.gemini ?? {}) as Record<string, unknown>;
  const groq = (sg.groq ?? {}) as Record<string, unknown>;
  const phrases = (sg.forbidden_phrases as string[]) ?? [];
  const a = data.speakers.A;
  const b = data.speakers.B;

  return {
    scriptGenerator: String(providers.script_generator ?? "fallback_chain"),
    geminiModel: String(gemini.model ?? "gemini-2.5-flash"),
    groqModel: String(groq.model ?? "openai/gpt-oss-20b"),
    duration: Number(sg.target_duration_minutes ?? 30),
    segments: Number(sg.num_segments ?? 6),
    pauseTurns: Number(tts.pause_between_turns_ms ?? 400),
    pauseSegments: Number(tts.pause_between_segments_ms ?? 900),
    forbidden: phrases.join("\n"),
    speakerAName: a?.name ?? "Maya",
    speakerAVoice: a?.voice_id ?? "af_heart",
    speakerBName: b?.name ?? "Theo",
    speakerBVoice: b?.voice_id ?? "am_michael",
  };
}

function applyForm(base: AppConfigResponse, form: FormState): AppConfigResponse {
  const config = structuredClone(base.config) as Record<string, unknown>;
  const speakers = structuredClone(base.speakers);

  const providers = {
    ...((config.providers as Record<string, unknown>) ?? {}),
    script_generator: form.scriptGenerator,
  };
  config.providers = providers;

  const sg: Record<string, unknown> = {
    ...((config.script_generation as Record<string, unknown>) ?? {}),
    target_duration_minutes: form.duration,
    num_segments: form.segments,
    forbidden_phrases: form.forbidden
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean),
  };
  sg.gemini = {
    ...((sg.gemini as Record<string, unknown>) ?? {}),
    model: form.geminiModel,
  };
  sg.groq = {
    ...((sg.groq as Record<string, unknown>) ?? {}),
    model: form.groqModel,
  };
  config.script_generation = sg;

  const tts = {
    ...((config.tts as Record<string, unknown>) ?? {}),
    pause_between_turns_ms: form.pauseTurns,
    pause_between_segments_ms: form.pauseSegments,
  };
  config.tts = tts;

  speakers.A = {
    ...speakers.A,
    name: form.speakerAName,
    voice_id: form.speakerAVoice,
  };
  speakers.B = {
    ...speakers.B,
    name: form.speakerBName,
    voice_id: form.speakerBVoice,
  };

  return { config, speakers };
}

function AssetUpload({
  name,
  label,
  bust,
  onUploaded,
}: {
  name: "speaker_a" | "speaker_b" | "logo";
  label: string;
  bust: number;
  onUploaded: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [exists, setExists] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch(assetUrl(name), { method: "HEAD" })
      .then((r) => {
        if (!cancelled) setExists(r.ok);
      })
      .catch(() => {
        if (!cancelled) setExists(false);
      });
    return () => {
      cancelled = true;
    };
  }, [name, bust]);

  async function onChange(file: File | null) {
    if (!file) return;
    setBusy(true);
    setErr(null);
    try {
      await uploadAsset(name, file);
      onUploaded();
    } catch (e) {
      if (axios.isAxiosError(e)) {
        const detail = e.response?.data?.detail;
        setErr(typeof detail === "string" ? detail : e.message);
      } else {
        setErr("Upload failed");
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-md border border-line bg-surface p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </p>
      <div className="mt-3 flex items-end gap-4">
        <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-md border border-line bg-surface">
          {exists ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${assetUrl(name)}?t=${bust}`}
              alt={label}
              className="h-full w-full object-cover"
            />
          ) : (
            <span className="px-2 text-center text-[11px] text-muted-foreground">No PNG</span>
          )}
        </div>
        <label className="cursor-pointer text-sm font-medium text-accent hover:text-accent-hover">
          {busy ? "Uploading…" : "Upload PNG"}
          <input
            type="file"
            accept="image/png"
            className="hidden"
            disabled={busy}
            onChange={(e) => onChange(e.target.files?.[0] ?? null)}
          />
        </label>
      </div>
      {err && <p className="mt-2 text-xs text-[var(--danger)]">{err}</p>}
    </div>
  );
}

export default function ConfigPage() {
  const [base, setBase] = useState<AppConfigResponse | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [assetBust, setAssetBust] = useState(Date.now());

  const load = useCallback(async () => {
    setLoading(true);
        try {
      const data = await getAppConfig();
      setBase(data);
      setForm(toForm(data));
    } catch {
      toast.error("Could not load configuration. Confirm the API is running.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function update<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!base || !form) return;
    setSaving(true);
    try {
      const payload = applyForm(base, form);
      await saveAppConfig(payload);
      setBase(payload);
      toast.success("Configuration saved. New episodes will use these settings.");
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        toast.error(typeof detail === "string" ? detail : err.message);
      } else {
        toast.error("Could not save configuration");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading || !form) {
    return <FormSkeleton />;
  }

  return (
    <PageShell variant="form">
      <PageHeader
        title="Config"
        description="Manage providers, episode length, speaker voices, and video assets from here. Day-to-day changes no longer require editing YAML."
      />

      <form onSubmit={onSubmit} className="flex flex-col gap-8">
        <SectionCard title="Providers">
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm sm:col-span-2">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Script generator
              </span>
              <select
                value={form.scriptGenerator}
                onChange={(e) => update("scriptGenerator", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              >
                {GENERATOR_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Gemini model
              </span>
              <input
                value={form.geminiModel}
                onChange={(e) => update("geminiModel", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Groq model
              </span>
              <input
                value={form.groqModel}
                onChange={(e) => update("groqModel", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
          </div>
        </SectionCard>

        <SectionCard title="Episode shape">
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Duration: {form.duration} minutes
              </span>
              <input
                type="range"
                min={5}
                max={60}
                value={form.duration}
                onChange={(e) => update("duration", Number(e.target.value))}
                className="accent-[var(--accent)]"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Segments
              </span>
              <input
                type="number"
                min={1}
                max={12}
                value={form.segments}
                onChange={(e) => update("segments", Number(e.target.value))}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Pause between turns (ms)
              </span>
              <input
                type="number"
                min={0}
                max={2000}
                value={form.pauseTurns}
                onChange={(e) => update("pauseTurns", Number(e.target.value))}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Pause between segments (ms)
              </span>
              <input
                type="number"
                min={0}
                max={3000}
                value={form.pauseSegments}
                onChange={(e) => update("pauseSegments", Number(e.target.value))}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm sm:col-span-2">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Forbidden phrases (one per line)
              </span>
              <textarea
                rows={5}
                value={form.forbidden}
                onChange={(e) => update("forbidden", e.target.value)}
                className="min-h-24 w-full rounded-md border border-line bg-surface px-3 py-2 font-mono text-xs outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
          </div>
        </SectionCard>

        <SectionCard title="Voices">
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Speaker A name
              </span>
              <input
                value={form.speakerAName}
                onChange={(e) => update("speakerAName", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Speaker A Kokoro voice
              </span>
              <input
                value={form.speakerAVoice}
                onChange={(e) => update("speakerAVoice", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Speaker B name
              </span>
              <input
                value={form.speakerBName}
                onChange={(e) => update("speakerBName", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                Speaker B Kokoro voice
              </span>
              <input
                value={form.speakerBVoice}
                onChange={(e) => update("speakerBVoice", e.target.value)}
                className="h-10 w-full rounded-md border border-line bg-surface px-3 text-sm outline-none transition-colors hover:border-ink/20 focus:border-accent focus:ring-2 focus:ring-accent/20"
              />
            </label>
          </div>
        </SectionCard>

        <div className="flex justify-end">
          <Button type="submit" disabled={saving} size="lg" className="rounded-md">
            {saving ? "Saving…" : "Save config"}
          </Button>
        </div>
      </form>

      <SectionCard
        title="Video assets"
        description="Optional PNG assets for the video stage. Missing files fall back to placeholders."
      >
        <div className="mt-5 grid gap-4 sm:grid-cols-3">
          <AssetUpload
            name="speaker_a"
            label="Speaker A"
            bust={assetBust}
            onUploaded={() => setAssetBust(Date.now())}
          />
          <AssetUpload
            name="speaker_b"
            label="Speaker B"
            bust={assetBust}
            onUploaded={() => setAssetBust(Date.now())}
          />
          <AssetUpload
            name="logo"
            label="Logo"
            bust={assetBust}
            onUploaded={() => setAssetBust(Date.now())}
          />
        </div>
      </SectionCard>
    </PageShell>
  );
}
