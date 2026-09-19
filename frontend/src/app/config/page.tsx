export default function ConfigPage() {
  return (
    <div className="animate-rise">
      <h1 className="font-serif text-3xl text-ink">Config</h1>
      <p className="mt-3 max-w-lg text-sm leading-relaxed text-muted">
        Edit providers, duration, voices, and assets here in a later step. For now use{" "}
        <code className="rounded bg-paper-deep px-1.5 py-0.5 text-ink">config/config.yaml</code>.
      </p>
    </div>
  );
}
