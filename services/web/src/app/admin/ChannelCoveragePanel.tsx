"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAdminApiBase } from "./apiBase";

interface ChannelRow {
  channel_id: string;
  slug: string;
  name: string;
  external_id: string | null;
  reported_videos: number | null;
  tracked_videos: number;
  // Optional — older deployed APIs may not return these (legacy
  // `collected_videos` was renamed to `transcribed_videos`).
  transcribed_videos?: number;
  cleaned_videos?: number;
  gap: number | null;
  metrics_sampled_at: string | null;
}

interface CoverageResponse {
  channels_total: number;
  channels_with_gap: number;
  total_gap: number;
  per_channel: ChannelRow[];
}

type SortField =
  | "name"
  | "reported"
  | "tracked"
  | "transcribed"
  | "cleaned"
  | "sampled";
type SortDir = "asc" | "desc";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-AU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  });
}

// Colour the downstream stage relative to its upstream parent. Anything
// that's a steep dropoff from the previous stage flags red.
function funnelClass(value: number | undefined, parent: number | null | undefined): string {
  if (value === undefined || parent === null || parent === undefined || parent === 0) {
    return "text-zinc-400";
  }
  const ratio = value / parent;
  if (ratio >= 0.95) return "text-green-400";
  if (ratio >= 0.5) return "text-yellow-400";
  return "text-red-400 font-semibold";
}

export default function ChannelCoveragePanel() {
  const { base } = useAdminApiBase();
  // Per-target cache: toggling LOCAL ↔ PROD shows previously-fetched data
  // instantly. First visit per target auto-fetches.
  const [cache, setCache] = useState<Map<string, CoverageResponse>>(() => new Map());
  const data = cache.get(base) ?? null;
  const fetchedTargets = useRef<Set<string>>(new Set());

  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [sortField, setSortField] = useState<SortField>("reported");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const fetchCoverage = useCallback(async () => {
    fetchedTargets.current.add(base);
    setLoading(true);
    setError(null);
    try {
      // onlyGaps is filtered client-side so toggling it doesn't refetch.
      const url = `${base}/api/admin/scout/channel-coverage`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json: CoverageResponse = await res.json();
      setCache((prev) => new Map(prev).set(base, json));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [base]);

  // Auto-fetch coverage once per target on first visit.
  useEffect(() => {
    if (!fetchedTargets.current.has(base)) {
      fetchCoverage();
    }
  }, [fetchCoverage, base]);

  // Reset error when toggling target (so an old error doesn't linger).
  useEffect(() => {
    setError(null);
  }, [base]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "name" ? "asc" : "desc");
    }
  };

  const visibleRows = useMemo(() => {
    if (!data) return [];
    const dir = sortDir === "asc" ? 1 : -1;
    const rows = onlyGaps
      ? data.per_channel.filter((r) => (r.gap ?? 0) > 0)
      : data.per_channel;
    return [...rows].sort((a, b) => {
      switch (sortField) {
        case "name":
          return dir * a.name.localeCompare(b.name);
        case "reported":
          return dir * ((a.reported_videos ?? -1) - (b.reported_videos ?? -1));
        case "tracked":
          return dir * (a.tracked_videos - b.tracked_videos);
        case "transcribed":
          return dir * ((a.transcribed_videos ?? -1) - (b.transcribed_videos ?? -1));
        case "cleaned":
          return dir * ((a.cleaned_videos ?? -1) - (b.cleaned_videos ?? -1));
        case "sampled": {
          const ta = a.metrics_sampled_at
            ? new Date(a.metrics_sampled_at).getTime()
            : 0;
          const tb = b.metrics_sampled_at
            ? new Date(b.metrics_sampled_at).getTime()
            : 0;
          return dir * (ta - tb);
        }
        default:
          return 0;
      }
    });
  }, [data, onlyGaps, sortField, sortDir]);

  const sortIndicator = (field: SortField) =>
    sortField === field ? (sortDir === "asc" ? " ▲" : " ▼") : "";

  return (
    <div className="rounded-lg border border-zinc-800">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="text-sm font-medium text-zinc-300">
          Channel Coverage
        </span>
        {data && (
          <span className="text-xs text-zinc-500">
            {data.channels_total} channels ·{" "}
            <span className="text-orange-400">
              {data.channels_with_gap} with gaps
            </span>{" "}
            ·{" "}
            <span className="text-red-400">
              {data.total_gap.toLocaleString()} videos missing
            </span>
          </span>
        )}
        <label className="ml-auto flex items-center gap-2 text-xs text-zinc-400">
          <input
            type="checkbox"
            checked={onlyGaps}
            onChange={(e) => setOnlyGaps(e.target.checked)}
            className="accent-orange-500"
          />
          Only gaps
        </label>
        <button
          onClick={fetchCoverage}
          disabled={loading}
          className="rounded bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
        >
          {loading ? "Loading..." : data ? "Refresh" : "Load coverage"}
        </button>
      </div>

      {error && (
        <div className="border-t border-zinc-800 px-4 py-3 text-sm text-red-400">
          Error: {error}
        </div>
      )}

      {!data && !error && !loading && (
        <div className="border-t border-zinc-800 px-4 py-6 text-center text-sm text-zinc-500">
          No data loaded. Click <span className="text-orange-400">Load coverage</span> to fetch.
        </div>
      )}

      {data && (
        <div className="overflow-x-auto border-t border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                <th
                  className="cursor-pointer select-none px-3 py-2 hover:text-zinc-300"
                  onClick={() => toggleSort("name")}
                >
                  Channel{sortIndicator("name")}
                </th>
                <th
                  className="cursor-pointer select-none px-3 py-2 text-right hover:text-zinc-300"
                  title="YouTube's reported video count (latest channel_metrics snapshot)"
                  onClick={() => toggleSort("reported")}
                >
                  Reported{sortIndicator("reported")}
                </th>
                <th
                  className="cursor-pointer select-none px-3 py-2 text-right hover:text-zinc-300"
                  title="Rows in the sources table for this channel"
                  onClick={() => toggleSort("tracked")}
                >
                  Tracked{sortIndicator("tracked")}
                </th>
                <th
                  className="cursor-pointer select-none px-3 py-2 text-right hover:text-zinc-300"
                  title="Sources whose transcript has been saved (s3_key set on document)"
                  onClick={() => toggleSort("transcribed")}
                >
                  Transcribed{sortIndicator("transcribed")}
                </th>
                <th
                  className="cursor-pointer select-none px-3 py-2 text-right hover:text-zinc-300"
                  title="Sources with at least one chunk where clean_text is populated"
                  onClick={() => toggleSort("cleaned")}
                >
                  Cleaned{sortIndicator("cleaned")}
                </th>
                <th
                  className="cursor-pointer select-none px-3 py-2 text-right hover:text-zinc-300"
                  onClick={() => toggleSort("sampled")}
                >
                  Last Snapshot{sortIndicator("sampled")}
                </th>
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => (
                <tr
                  key={row.channel_id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-900/50"
                >
                  <td className="px-3 py-2">
                    <a
                      href={`/wiki/channel/${row.slug}`}
                      className="text-orange-400 hover:text-orange-300 hover:underline"
                    >
                      {row.name}
                    </a>
                    {row.external_id && (
                      <span className="ml-2 font-mono text-[10px] text-zinc-600">
                        {row.external_id}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right text-zinc-300">
                    {row.reported_videos !== null
                      ? row.reported_videos.toLocaleString()
                      : "—"}
                  </td>
                  <td
                    className={`px-3 py-2 text-right ${funnelClass(
                      row.tracked_videos,
                      row.reported_videos,
                    )}`}
                  >
                    {row.tracked_videos.toLocaleString()}
                  </td>
                  <td
                    className={`px-3 py-2 text-right ${funnelClass(
                      row.transcribed_videos,
                      row.tracked_videos,
                    )}`}
                  >
                    {row.transcribed_videos !== undefined
                      ? row.transcribed_videos.toLocaleString()
                      : "—"}
                  </td>
                  <td
                    className={`px-3 py-2 text-right ${funnelClass(
                      row.cleaned_videos,
                      row.transcribed_videos,
                    )}`}
                  >
                    {row.cleaned_videos !== undefined
                      ? row.cleaned_videos.toLocaleString()
                      : "—"}
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-right text-zinc-500">
                    {formatDate(row.metrics_sampled_at)}
                  </td>
                </tr>
              ))}
              {visibleRows.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-3 py-6 text-center text-zinc-600"
                  >
                    {onlyGaps ? "No gaps — coverage is clean." : "No channels."}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
