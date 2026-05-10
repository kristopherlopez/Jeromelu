import { apiFetch } from "@/lib/api";
import type { SourceListResponse } from "@/lib/types";
import SourceListClient from "./SourceListClient";

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Sources | The Wiki | Jaromelu",
  description: "Processed transcript sources Jaromelu has ingested.",
};

export default async function SourcesPage() {
  let data: SourceListResponse;
  try {
    data = await apiFetch<SourceListResponse>("/api/sources");
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="text-zinc-500">Failed to load sources: {msg}</p>
      </main>
    );
  }

  if (data.items.length === 0) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="text-zinc-500">No sources yet.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen px-6 py-8 sm:px-8">
      <div className="mx-auto max-w-4xl">
        <h1
          className="mb-6 text-xl font-bold tracking-tight"
          style={{ color: "var(--tigers-orange)" }}
        >
          Sources
        </h1>
      </div>
      <SourceListClient sources={data.items} />
    </main>
  );
}
