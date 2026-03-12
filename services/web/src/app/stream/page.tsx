import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { SourceListResponse } from "@/lib/types";

export const dynamic = "force-dynamic";

export default async function StreamPage() {
  let data: SourceListResponse;
  try {
    data = await apiFetch<SourceListResponse>("/api/sources");
  } catch {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="text-zinc-500">Failed to load sources. Is the API running?</p>
      </main>
    );
  }

  if (data.items.length === 0) {
    return (
      <main className="flex min-h-screen items-center justify-center p-8">
        <p className="text-zinc-500">No processed sources yet.</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-8">
      <h1
        className="mb-6 text-2xl font-bold"
        style={{ color: "var(--tigers-orange)" }}
      >
        Source Review
      </h1>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {data.items.map((source) => (
          <Link
            key={source.source_id}
            href={`/stream/${source.source_id}`}
            className="group rounded-lg border border-zinc-800 p-4 transition-colors hover:border-zinc-600 hover:bg-zinc-900/50"
          >
            <h2 className="mb-1 text-sm font-semibold text-zinc-200 group-hover:text-white line-clamp-2">
              {source.title}
            </h2>
            {source.creator_name && (
              <p className="mb-2 text-xs text-zinc-500">{source.creator_name}</p>
            )}
            <div className="flex items-center gap-3 text-xs text-zinc-500">
              <span
                className="font-medium"
                style={{ color: "var(--tigers-orange)" }}
              >
                {source.claim_count} claims
              </span>
              {source.published_at && (
                <span>
                  {new Date(source.published_at).toLocaleDateString("en-AU", {
                    day: "numeric",
                    month: "short",
                    year: "numeric",
                  })}
                </span>
              )}
            </div>
          </Link>
        ))}
      </div>
    </main>
  );
}
