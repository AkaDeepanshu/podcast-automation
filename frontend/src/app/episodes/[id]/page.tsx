export default function EpisodeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  return <EpisodeDetail params={params} />;
}

async function EpisodeDetail({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <div className="animate-rise">
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.18em] text-accent">
        Episode
      </p>
      <h1 className="font-serif text-3xl text-ink">{id}</h1>
      <p className="mt-3 max-w-lg text-sm leading-relaxed text-muted">
        Detail view arrives in the next step — stage tracker, live logs, and media players.
      </p>
    </div>
  );
}
