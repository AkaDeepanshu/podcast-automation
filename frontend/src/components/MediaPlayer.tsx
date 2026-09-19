"use client";

import { useEffect, useState } from "react";
import {
  audioUrl,
  getScript,
  videoUrl,
  type DialogueLine,
} from "@/lib/api";

type Props = {
  jobId: string;
  hasScript: boolean;
  hasAudio: boolean;
  hasVideo: boolean;
};

export function MediaPlayer({
  jobId,
  hasScript,
  hasAudio,
  hasVideo,
}: Props) {
  const [script, setScript] = useState<DialogueLine[] | null>(null);
  const [scriptOpen, setScriptOpen] = useState(false);
  const [scriptError, setScriptError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasScript) {
      setScript(null);
      return;
    }
    let cancelled = false;
    getScript(jobId)
      .then((lines) => {
        if (!cancelled) {
          setScript(lines);
          setScriptError(null);
        }
      })
      .catch(() => {
        if (!cancelled) setScriptError("Script not available yet");
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, hasScript]);

  return (
    <section className="rounded-[var(--radius)] border border-line bg-surface/90 p-5 shadow-[var(--shadow)] sm:p-6">
      <h2 className="mb-5 font-serif text-xl text-ink">Outputs</h2>

      <div className="flex flex-col gap-6">
        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Script
            </h3>
            {hasScript && (
              <button
                type="button"
                onClick={() => setScriptOpen((v) => !v)}
                className="text-xs font-medium text-accent transition hover:text-accent-hover"
              >
                {scriptOpen ? "Collapse" : "Expand dialogue"}
              </button>
            )}
          </div>
          {!hasScript && (
            <p className="text-sm text-muted">Script will appear after the script stage finishes.</p>
          )}
          {scriptError && <p className="text-sm text-[var(--danger)]">{scriptError}</p>}
          {scriptOpen && script && (
            <div className="max-h-80 overflow-y-auto rounded-xl border border-line bg-paper/70 p-4">
              <ul className="flex flex-col gap-3">
                {script.map((line, i) => (
                  <li key={i} className="text-sm leading-relaxed">
                    <span className="font-semibold text-accent">
                      {line.speaker}
                    </span>
                    <span className="text-ink-soft"> — {line.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasScript && !scriptOpen && script && (
            <p className="text-sm text-muted">
              {script.length} dialogue lines ready
            </p>
          )}
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Audio
            </h3>
            {hasAudio && (
              <a
                href={audioUrl(jobId)}
                download={`${jobId}.wav`}
                className="text-xs font-medium text-accent transition hover:text-accent-hover"
              >
                Download WAV
              </a>
            )}
          </div>
          {hasAudio ? (
            <audio controls className="w-full" src={audioUrl(jobId)} preload="metadata" />
          ) : (
            <p className="text-sm text-muted">Final audio appears after assembly.</p>
          )}
        </div>

        <div>
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="text-xs font-semibold uppercase tracking-[0.16em] text-muted">
              Video
            </h3>
            {hasVideo && (
              <a
                href={videoUrl(jobId)}
                download={`${jobId}.mp4`}
                className="text-xs font-medium text-accent transition hover:text-accent-hover"
              >
                Download MP4
              </a>
            )}
          </div>
          {hasVideo ? (
            <video
              controls
              className="w-full overflow-hidden rounded-xl border border-line bg-ink"
              src={videoUrl(jobId)}
              preload="metadata"
            />
          ) : (
            <p className="text-sm text-muted">
              Video appears when the video stage completes (or was not skipped).
            </p>
          )}
        </div>
      </div>
    </section>
  );
}
