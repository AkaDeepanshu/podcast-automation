"use client";

/** Episode detail — StageTracker, LogStream, media outputs. Step 5. */
export default function EpisodeDetailPage({ params }) {
  return (
    <main className="min-h-screen p-8">
      <h1 className="text-2xl font-semibold">Episode {params?.id}</h1>
      <p className="mt-2 text-neutral-500">Step 5 — stage tracker, logs, players.</p>
    </main>
  );
}
