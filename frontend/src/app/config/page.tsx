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
import { useToast } from "@/components/Toaster";

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
    <div className="rounded-xl border border-line bg-paper/50 p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
        {label}
      </p>
      <div className="mt-3 flex items-end gap-4">
        <div className="flex h-24 w-24 items-center justify-center overflow-hidden rounded-xl border border-line bg-surface">
          {exists ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={`${assetUrl(name)}?t=${bust}`}
              alt={label}
              className="h-full w-full object-cover"
            />
          ) : (
            <span className="px-2 text-center text-[11px] text-muted">No PNG</span>
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
  const { success, error: toastError } = useToast();
  const [assetBust, setAssetBust] = useState(Date.now());

  const load = useCallback(async () => {
    setLoading(true);
        try {
      const data = await getAppConfig();
      setBase(data);
      setForm(toForm(data));
    } catch {
      toastError("Could not load config. Is the API running?");
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
      success("Saved. New episodes will use these settings.");
    } catch (err) {
      if (axios.isAxiosError(err)) {
        const detail = err.response?.data?.detail;
        toastError(typeof detail === "string" ? detail : err.message);
      } else {
        toastError("Save failed");
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading || !form) {
    return <p className="animate-rise text-sm text-muted">Loading config…</p>;
  }

  return (
    <div className="animate-rise mx-auto max-w-3xl">
      <div className="mb-8">
        <h1 className="font-serif text-2xl sm:text-[1.75rem] text-ink">Config</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">
          Providers, episode shape, voices, and video assets — no more hand-editing YAML for
          day-to-day use.
        </p>
      </div>


      <form onSubmit={onSubmit} className="flex flex-col gap-8">
        <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
          <h2 className="font-serif text-xl text-ink">Providers</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm sm:col-span-2">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Script generator
              </span>
              <select
                value={form.scriptGenerator}
                onChange={(e) => update("scriptGenerator", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              >
                {GENERATOR_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Gemini model
              </span>
              <input
                value={form.geminiModel}
                onChange={(e) => update("geminiModel", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Groq model
              </span>
              <input
                value={form.groqModel}
                onChange={(e) => update("groqModel", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
          </div>
        </section>

        <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
          <h2 className="font-serif text-xl text-ink">Episode shape</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Duration (minutes) — {form.duration}
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
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Segments
              </span>
              <input
                type="number"
                min={1}
                max={12}
                value={form.segments}
                onChange={(e) => update("segments", Number(e.target.value))}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Pause between turns (ms)
              </span>
              <input
                type="number"
                min={0}
                max={2000}
                value={form.pauseTurns}
                onChange={(e) => update("pauseTurns", Number(e.target.value))}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Pause between segments (ms)
              </span>
              <input
                type="number"
                min={0}
                max={3000}
                value={form.pauseSegments}
                onChange={(e) => update("pauseSegments", Number(e.target.value))}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm sm:col-span-2">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Forbidden phrases (one per line)
              </span>
              <textarea
                rows={5}
                value={form.forbidden}
                onChange={(e) => update("forbidden", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 font-mono text-xs outline-none focus:border-accent"
              />
            </label>
          </div>
        </section>

        <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
          <h2 className="font-serif text-xl text-ink">Voices</h2>
          <div className="mt-5 grid gap-4 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Speaker A name
              </span>
              <input
                value={form.speakerAName}
                onChange={(e) => update("speakerAName", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Speaker A Kokoro voice
              </span>
              <input
                value={form.speakerAVoice}
                onChange={(e) => update("speakerAVoice", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Speaker B name
              </span>
              <input
                value={form.speakerBName}
                onChange={(e) => update("speakerBName", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm">
              <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
                Speaker B Kokoro voice
              </span>
              <input
                value={form.speakerBVoice}
                onChange={(e) => update("speakerBVoice", e.target.value)}
                className="rounded-xl border border-line bg-paper px-4 py-3 outline-none focus:border-accent"
              />
            </label>
          </div>
        </section>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="rounded-xl bg-accent px-6 py-3 text-sm font-semibold text-white transition hover:bg-accent-hover disabled:opacity-50"
          >
            {saving ? "Saving…" : "Save config"}
          </button>
        </div>
      </form>

      <section className="mt-10 rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
        <h2 className="font-serif text-xl text-ink">Video assets</h2>
        <p className="mt-1 text-sm text-muted">
          Optional PNGs for the video stage. Missing assets use placeholders.
        </p>
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
      </section>
    </div>
  );
}
