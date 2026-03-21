"use client";

export function StatusLine() {
  // TODO: Pull real status from orchestrator/worker API
  // For now, always show the idle watching state
  const status = "Watching the market";

  return (
    <div className="flex items-center gap-2 rounded-full border border-zinc-800 px-4 py-2 text-sm text-zinc-500">
      <span className="relative flex h-2 w-2">
        <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
        <span className="relative inline-flex h-2 w-2 rounded-full bg-[var(--tigers-orange)]" />
      </span>
      {status}
    </div>
  );
}
