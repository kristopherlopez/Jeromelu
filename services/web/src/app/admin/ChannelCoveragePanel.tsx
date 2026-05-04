"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAdminApiBase } from "./apiBase";

interface ChannelRow {
  channel_id: string;
  slug: string;
  name: string;
  external_id: string | null;
  reported_videos: number | null;
  tracked_videos: number;
  // Optional — older deployed APIs (prod, pre-rename) don't return these.
  collected_videos?: number;
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
  | "collected"
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
  const [data, setData] = useState<CoverageResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [onlyGaps, setOnlyGaps] = useState(false);
  const [sortField, setSortField] = useState<SortField>("reported");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const fetchCoverage = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const url = `${base}/api/admin/scout/channel-coverage${
        onlyGaps ? "?only_gaps=true" : ""
      }`;
      const res = await fetch(url);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [base, onlyGaps]);

  useEffect(() => {
    fetchCoverage();
  }, [fetchCoverage]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "name" ? "asc" : "desc");
    }
  };

  const sortedRows = useMemo(() => {
    if (!data) return [];
    const dir = sortDir === "asc" ? 1 : -1;
    return [...data.per_channel].sort((a, b) => {
      switch (sortField) {
        case "name":
          return dir * a.name.localeCompare(b.name);
        case "reported":
          return dir * ((a.reported_videos ?? -1) - (b.reported_videos ?? -1));
        case "tracked":
          return dir * (a.tracked_videos - b.tracked_videos);
        case "collected":
          return dir * ((a.collected_videos ?? -1) - (b.collected_videos ?? -1));
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
  }, [data, sortField, sortDir]);

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
          className="rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
        >
          {loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {error && (
        <div className="border-t border-zinc-800 px-4 py-3 text-sm text-red-400">
          Error: {error}
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
                  title="Sources whose transcript has been saved (s3_key or chunks present)"
                  onClick={() => toggleSort("collected")}
                >
                  Collected{sortIndicator("collected")}
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
              {sortedRows.map((row) => (
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
                      row.collected_videos,
                      row.tracked_videos,
                    )}`}
                  >
                    {row.collected_videos !== undefined
                      ? row.collected_videos.toLocaleString()
                      : "—"}
                  </td>
                  <td
                    className={`px-3 py-2 text-right ${funnelClass(
                      row.cleaned_videos,
                      row.collected_videos,
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
              {sortedRows.length === 0 && (
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
