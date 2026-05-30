"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import ChannelCoveragePanel from "./ChannelCoveragePanel";
import PresentersPanel from "./PresentersPanel";
import ReconCandidatesPanel from "./ReconCandidatesPanel";
import ScoutDashboardPanel from "./ScoutDashboardPanel";
import { ADMIN_API_TARGETS, AdminApiTarget, useAdminApiBase } from "./apiBase";

// --- Types ---

interface PipelineStages {
  registered: boolean;
  transcribed: boolean;
  chunked: boolean;
  cleaned: boolean;
  extracted: boolean;
}

interface PipelineItem {
  source_id: string;
  title: string;
  channel_name: string | null;
  video_id: string | null;
  published_at: string | null;
  stages: PipelineStages;
  chunk_count: number;
  claim_count: number;
}

interface PipelineSummary {
  total: number;
  by_stage: Record<string, number>;
}

interface PipelineItemsResponse {
  items: PipelineItem[];
  total: number;
  limit: number;
  offset: number;
}

interface SyncItem {
  video_id: string;
  local_raw: boolean;
  local_clean: boolean;
  local_claims: boolean;
  minio_raw: boolean;
  minio_clean: boolean;
  in_db: boolean;
}

interface SyncResponse {
  summary: Record<string, number>;
  items: SyncItem[];
}

type StageKey = keyof PipelineStages;
const STAGES: StageKey[] = ["registered", "transcribed", "chunked", "cleaned", "extracted"];
// Per-row column set excludes "registered" — it's true for every source so
// the checkmark is always on, adding noise without information.
const TABLE_STAGES: StageKey[] = STAGES.filter((s) => s !== "registered");

const STAGE_DESCRIPTIONS: Record<StageKey, string> = {
  registered: "Source row exists in the DB",
  transcribed: "Transcript saved (s3_key set on document)",
  chunked: "Chunks loaded into DB (chunk_count > 0)",
  cleaned: "At least one chunk has clean_text populated",
  extracted: "At least one Claim row has been extracted",
};

interface TestFile {
  filename: string;
  title: string;
  has_raw: boolean;
}

interface DiffEntry {
  index: number;
  start: number;
  raw: string;
  test: string;
}

interface DiffResponse {
  title: string;
  total_segments: number;
  diff_count: number;
  diffs: DiffEntry[];
}

type SortField = "title" | "published_at" | "chunk_count" | "claim_count";
type SortDir = "asc" | "desc";

// --- Helpers ---

function StageCell({ done }: { done: boolean }) {
  return done ? (
    <span className="text-green-400">&#10003;</span>
  ) : (
    <span className="text-zinc-600">&mdash;</span>
  );
}

function SyncCell({ present }: { present: boolean }) {
  return present ? (
    <span className="text-green-400">&#10003;</span>
  ) : (
    <span className="text-red-400">&#10007;</span>
  );
}

function SortHeader({
  field,
  label,
  current,
  dir,
  onSort,
  className = "",
}: {
  field: SortField;
  label: string;
  current: SortField;
  dir: SortDir;
  onSort: (f: SortField) => void;
  className?: string;
}) {
  const active = current === field;
  return (
    <th
      className={`cursor-pointer select-none px-3 py-2 hover:text-zinc-300 ${className}`}
      onClick={() => onSort(field)}
    >
      {label}
      <span className="ml-1">
        {active ? (dir === "asc" ? "▲" : "▼") : ""}
      </span>
    </th>
  );
}

// --- Diff helpers ---

function highlightDiff(raw: string, test: string): { rawParts: React.ReactNode[]; testParts: React.ReactNode[] } {
  // Simple word-level diff highlighting
  const rawWords = raw.split(/(\s+)/);
  const testWords = test.split(/(\s+)/);

  const rawParts: React.ReactNode[] = [];
  const testParts: React.ReactNode[] = [];

  const maxLen = Math.max(rawWords.length, testWords.length);

  for (let i = 0; i < maxLen; i++) {
    const rw = i < rawWords.length ? rawWords[i] : "";
    const tw = i < testWords.length ? testWords[i] : "";

    if (rw === tw) {
      rawParts.push(rw);
      testParts.push(tw);
    } else {
      if (rw) rawParts.push(<span key={`r${i}`} className="bg-red-900/60 text-red-300 rounded px-0.5">{rw}</span>);
      if (tw) testParts.push(<span key={`t${i}`} className="bg-green-900/60 text-green-300 rounded px-0.5">{tw}</span>);
    }
  }

  return { rawParts, testParts };
}

function formatTs(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function TranscriptDiffPanel() {
  const { base } = useAdminApiBase();
  const [files, setFiles] = useState<TestFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [diff, setDiff] = useState<DiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${base}/api/admin/transcript-test-files`)
      .then((r) => r.json())
      .then((data) => {
        setFiles(data.files ?? []);
        if (data.files?.length === 1) {
          setSelectedFile(data.files[0].filename);
        }
      })
      .catch(() => {});
  }, [base]);

  useEffect(() => {
    if (!selectedFile) return;
    setLoading(true);
    setError(null);
    setDiff(null);
    fetch(`${base}/api/admin/transcript-diff/${encodeURIComponent(selectedFile)}`)
      .then((r) => {
        if (!r.ok) throw new Error(`${r.status}`);
        return r.json();
      })
      .then((data) => setDiff(data))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [base, selectedFile]);

  if (files.length === 0) return null;

  return (
    <div className="rounded-lg border border-zinc-800">
      <div className="flex items-center gap-3 px-4 py-3">
        <span className="text-sm font-medium text-zinc-300">Transcript Diff</span>
        {files.length > 1 && (
          <select
            value={selectedFile ?? ""}
            onChange={(e) => setSelectedFile(e.target.value || null)}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-white"
          >
            <option value="">Select file...</option>
            {files.map((f) => (
              <option key={f.filename} value={f.filename}>
                {f.title}
              </option>
            ))}
          </select>
        )}
        {diff && (
          <span className="ml-auto text-xs text-zinc-500">
            {diff.diff_count} differences / {diff.total_segments} segments
          </span>
        )}
      </div>

      {loading && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          Loading diff...
        </div>
      )}

      {error && (
        <div className="border-t border-zinc-800 px-4 py-3 text-sm text-red-400">
          Error: {error}
        </div>
      )}

      {diff && diff.diffs.length > 0 && (
        <div className="border-t border-zinc-800">
          {/* Column headers */}
          <div className="grid grid-cols-[60px_1fr_1fr] border-b border-zinc-800 px-2 py-1.5 text-xs font-medium text-zinc-500">
            <div>Seg</div>
            <div>Raw (auto-caption)</div>
            <div>Test (corrected)</div>
          </div>

          {/* Diff rows */}
          <div className="max-h-[600px] overflow-y-auto">
            {diff.diffs.map((d) => {
              const { rawParts, testParts } = highlightDiff(d.raw, d.test);
              return (
                <div
                  key={d.index}
                  className="grid grid-cols-[60px_1fr_1fr] border-b border-zinc-800/50 px-2 py-1.5 text-sm hover:bg-zinc-900/50"
                >
                  <div className="text-xs text-zinc-600 pt-0.5">
                    <div>{d.index}</div>
                    <div className="text-[10px]">{formatTs(d.start)}</div>
                  </div>
                  <div className="pr-2 text-zinc-400 break-words">{rawParts}</div>
                  <div className="pl-2 border-l border-zinc-800 text-zinc-300 break-words">{testParts}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {diff && diff.diffs.length === 0 && (
        <div className="border-t border-zinc-800 px-4 py-6 text-center text-sm text-green-400">
          No differences — raw and test files are identical.
        </div>
      )}
    </div>
  );
}

// --- Component ---

type AdminTab = "video" | "scout" | "coverage" | "recon" | "presenters" | "diff";

const TABS: { id: AdminTab; label: string }[] = [
  { id: "video", label: "Video Processing" },
  { id: "scout", label: "Scout Dashboard" },
  { id: "coverage", label: "Channel Coverage" },
  { id: "recon", label: "Recon Review" },
  { id: "presenters", label: "Presenters" },
  { id: "diff", label: "Transcript Diff" },
];

export default function AdminClient() {
  const { base, target, setTarget } = useAdminApiBase();
  const [activeTab, setActiveTab] = useState<AdminTab>("video");

  // Per-target cache for the cheap summary endpoint (5 SQL counts, ~50 bytes).
  // Items are NOT cached per-target — paginated payloads are small (~25 KB)
  // and the cache invalidation rules across (base, stage, search, sort, page)
  // aren't worth the complexity. Toggle is fast either way.
  const [summaryCache, setSummaryCache] = useState<Map<string, PipelineSummary>>(
    () => new Map(),
  );
  const [syncCache, setSyncCache] = useState<Map<string, SyncResponse>>(() => new Map());
  const summary = summaryCache.get(base) ?? null;
  const sync = syncCache.get(base) ?? null;
  const fetchedSummaryTargets = useRef<Set<string>>(new Set());

  const [items, setItems] = useState<PipelineItem[]>([]);
  const [itemsTotal, setItemsTotal] = useState(0);

  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);

  const [stageFilter, setStageFilter] = useState<StageKey | "all">("all");
  const [search, setSearch] = useState("");
  // Debounced mirror of `search` — only this drives fetches, so per-keystroke
  // typing doesn't spam the API while pagination clicks fire immediately.
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("published_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [page, setPage] = useState(0);
  const [pageSize, setPageSize] = useState(50);

  const fetchSummary = useCallback(async () => {
    fetchedSummaryTargets.current.add(base);
    try {
      const res = await fetch(`${base}/api/admin/pipeline/summary`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: PipelineSummary = await res.json();
      setSummaryCache((prev) => new Map(prev).set(base, data));
    } catch (e) {
      setPipelineError(e instanceof Error ? e.message : String(e));
    }
  }, [base]);

  const fetchItems = useCallback(async () => {
    setPipelineLoading(true);
    setPipelineError(null);
    try {
      const params = new URLSearchParams({
        sort: `${sortField}:${sortDir}`,
        limit: String(pageSize),
        offset: String(page * pageSize),
      });
      if (stageFilter !== "all") params.set("stage", stageFilter);
      if (debouncedSearch.trim()) params.set("search", debouncedSearch.trim());
      const res = await fetch(`${base}/api/admin/pipeline/items?${params.toString()}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: PipelineItemsResponse = await res.json();
      setItems(data.items);
      setItemsTotal(data.total);
    } catch (e) {
      setPipelineError(e instanceof Error ? e.message : String(e));
    } finally {
      setPipelineLoading(false);
    }
  }, [base, stageFilter, debouncedSearch, sortField, sortDir, page, pageSize]);

  const refreshAll = useCallback(() => {
    fetchSummary();
    fetchItems();
  }, [fetchSummary, fetchItems]);

  const fetchSync = useCallback(async () => {
    setSyncLoading(true);
    setSyncError(null);
    try {
      const res = await fetch(`${base}/api/admin/sync-status`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data: SyncResponse = await res.json();
      setSyncCache((prev) => new Map(prev).set(base, data));
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncLoading(false);
    }
  }, [base]);

  // Auto-fetch summary once per target on first visit. Always cheap.
  useEffect(() => {
    if (!fetchedSummaryTargets.current.has(base)) {
      fetchSummary();
    }
  }, [fetchSummary, base]);

  // Auto-fetch items immediately on filter / sort / page change. Search is
  // debounced via the `debouncedSearch` mirror above.
  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(t);
  }, [search]);

  // Reset to page 0 when filter / search / sort / page size changes — sitting
  // on page 47 of a freshly-filtered 3-row result is not useful.
  useEffect(() => {
    setPage(0);
  }, [stageFilter, debouncedSearch, sortField, sortDir, pageSize]);

  // Reset transient errors when toggling target (so an old error doesn't linger).
  useEffect(() => {
    setPipelineError(null);
    setSyncError(null);
  }, [base]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "title" ? "asc" : "desc");
    }
  };

  const totalPages = Math.max(1, Math.ceil(itemsTotal / pageSize));
  const showingFrom = itemsTotal === 0 ? 0 : page * pageSize + 1;
  const showingTo = Math.min(itemsTotal, (page + 1) * pageSize);

  return (
    <div className="space-y-6">
      {/* API target toggle */}
      <div className="flex items-center justify-between rounded-lg border border-zinc-800 bg-zinc-900/40 px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-zinc-400">API target</span>
          <div className="flex overflow-hidden rounded border border-zinc-700">
            {(Object.keys(ADMIN_API_TARGETS) as AdminApiTarget[]).map((t) => {
              const active = target === t;
              return (
                <button
                  key={t}
                  onClick={() => setTarget(t)}
                  className={`px-3 py-1 text-xs font-medium uppercase tracking-wider transition-colors ${
                    active
                      ? "bg-orange-600 text-white"
                      : "bg-zinc-900 text-zinc-400 hover:text-zinc-200"
                  }`}
                >
                  {t}
                </button>
              );
            })}
          </div>
        </div>
        <span className="font-mono text-[11px] text-zinc-500">{base}</span>
      </div>

      {/* Tab nav */}
      <div className="flex gap-1 border-b border-zinc-800">
        {TABS.map((t) => {
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => setActiveTab(t.id)}
              className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
                active
                  ? "border-orange-500 text-orange-400"
                  : "border-transparent text-zinc-500 hover:text-zinc-300"
              }`}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      {/* Tab: Video Processing — keep mounted to preserve filter/sort state */}
      <div className={activeTab === "video" ? "space-y-8" : "hidden"}>
      {/* Always-visible refresh strip */}
      <div className="flex items-center justify-end">
        <button
          onClick={refreshAll}
          disabled={pipelineLoading}
          className="rounded bg-orange-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
        >
          {pipelineLoading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {/* Section 1: Summary Cards (auto-fetched on tab open from /pipeline/summary) */}
      {summary && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {STAGES.map((stage) => (
            <div
              key={stage}
              title={STAGE_DESCRIPTIONS[stage]}
              className="cursor-help rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-center"
            >
              <div className="text-2xl font-bold text-white">
                {summary.by_stage[stage] ?? 0}
              </div>
              <div className="mt-1 text-xs font-medium capitalize text-zinc-400">
                {stage}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Stage legend */}
      <div className="grid grid-cols-1 gap-1 rounded-lg border border-zinc-800 bg-zinc-900/30 p-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
        {STAGES.map((s) => (
          <div key={s} className="flex gap-2">
            <span className="w-20 shrink-0 font-medium capitalize text-zinc-300">
              {s}
            </span>
            <span className="text-zinc-500">{STAGE_DESCRIPTIONS[s]}</span>
          </div>
        ))}
      </div>

      {pipelineError && (
        <p className="text-red-400 text-sm">Pipeline error: {pipelineError}</p>
      )}

      {/* Section 2: Pipeline Table — server-side filter, sort, paginate */}
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <select
            value={stageFilter}
            onChange={(e) => setStageFilter(e.target.value as StageKey | "all")}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white"
            title="Stage filter — selects on the highest reached stage exactly (e.g. 'Transcribed' = saved but not yet chunked)"
          >
            <option value="all">All stages</option>
            {STAGES.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
          <input
            type="text"
            placeholder="Search title or video id..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white placeholder:text-zinc-600 focus:border-orange-500 focus:outline-none"
          />
          <select
            value={pageSize}
            onChange={(e) => setPageSize(Number(e.target.value))}
            className="ml-auto rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white"
            title="Rows per page"
          >
            {[50, 100, 200].map((n) => (
              <option key={n} value={n}>
                {n} / page
              </option>
            ))}
          </select>
        </div>

        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                <th className="px-3 py-2">Channel</th>
                <SortHeader field="title" label="Title" current={sortField} dir={sortDir} onSort={toggleSort} />
                <SortHeader field="published_at" label="Published" current={sortField} dir={sortDir} onSort={toggleSort} />
                {TABLE_STAGES.map((s) => (
                  <th
                    key={s}
                    title={STAGE_DESCRIPTIONS[s]}
                    className="cursor-help px-3 py-2 text-center capitalize"
                  >
                    {s.slice(0, 4)}
                  </th>
                ))}
                <SortHeader field="chunk_count" label="Chunks" current={sortField} dir={sortDir} onSort={toggleSort} className="text-center" />
                <SortHeader field="claim_count" label="Claims" current={sortField} dir={sortDir} onSort={toggleSort} className="text-center" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.source_id}
                  className="border-b border-zinc-800/50 hover:bg-zinc-900/50"
                >
                  <td className="max-w-[12rem] truncate px-3 py-2 text-zinc-400">
                    {item.channel_name ?? "—"}
                  </td>
                  <td className="max-w-xs truncate px-3 py-2">
                    <a
                      href={`/wiki/source/${item.source_id}`}
                      className="text-orange-400 hover:text-orange-300 hover:underline"
                    >
                      {item.title}
                    </a>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-zinc-500">
                    {item.published_at
                      ? new Date(item.published_at).toLocaleDateString("en-AU", { day: "2-digit", month: "2-digit", year: "numeric" })
                      : "—"}
                  </td>
                  {TABLE_STAGES.map((s) => (
                    <td key={s} className="px-3 py-2 text-center">
                      <StageCell done={item.stages[s]} />
                    </td>
                  ))}
                  <td className="px-3 py-2 text-center text-zinc-400">
                    {item.chunk_count}
                  </td>
                  <td className="px-3 py-2 text-center text-zinc-400">
                    {item.claim_count}
                  </td>
                </tr>
              ))}
              {items.length === 0 && !pipelineLoading && (
                <tr>
                  <td
                    colSpan={3 + TABLE_STAGES.length + 2}
                    className="px-3 py-6 text-center text-zinc-600"
                  >
                    No sources match.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination strip */}
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3 text-xs text-zinc-500">
          <span>
            {itemsTotal === 0
              ? "0 results"
              : `Showing ${showingFrom.toLocaleString()}–${showingTo.toLocaleString()} of ${itemsTotal.toLocaleString()}`}
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || pipelineLoading}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
            >
              ‹ Prev
            </button>
            <span className="px-1">
              Page {page + 1} of {totalPages.toLocaleString()}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page + 1 >= totalPages || pipelineLoading}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1 text-zinc-300 hover:bg-zinc-800 disabled:opacity-40"
            >
              Next ›
            </button>
          </div>
        </div>
      </div>

      {/* Section 3: Sync Status (expandable) */}
      <div className="rounded-lg border border-zinc-800">
        <button
          onClick={() => {
            setSyncOpen(!syncOpen);
            if (!syncOpen && !sync) fetchSync();
          }}
          className="flex w-full items-center justify-between px-4 py-3 text-sm font-medium text-zinc-300 hover:text-white"
        >
          <span>Sync Status</span>
          <span className="text-zinc-600">{syncOpen ? "▲" : "▼"}</span>
        </button>

        {syncOpen && (
          <div className="border-t border-zinc-800 px-4 py-4">
            <button
              onClick={fetchSync}
              disabled={syncLoading}
              className="mb-4 rounded bg-orange-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
            >
              {syncLoading ? "Checking..." : "Check Sync"}
            </button>

            {syncError && (
              <p className="mb-3 text-red-400 text-sm">
                Sync error: {syncError}
              </p>
            )}

            {sync && (
              <>
                <div className="mb-4 flex flex-wrap gap-4 text-xs text-zinc-400">
                  <span>{sync.summary.total_videos} total videos</span>
                  <span className="text-orange-400">
                    {sync.summary.mismatches} mismatches
                  </span>
                  <span>
                    {sync.summary.local_not_in_minio} local not in MinIO
                  </span>
                  <span>
                    {sync.summary.minio_not_in_db} MinIO not in DB
                  </span>
                  <span>
                    {sync.summary.db_not_in_minio} DB not in MinIO
                  </span>
                </div>

                {sync.items.length === 0 ? (
                  <p className="text-sm text-green-400">
                    All sources are in sync.
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead>
                        <tr className="border-b border-zinc-800 text-left text-zinc-500">
                          <th className="px-2 py-1.5">Video ID</th>
                          <th className="px-2 py-1.5 text-center">
                            Local Raw
                          </th>
                          <th className="px-2 py-1.5 text-center">
                            Local Clean
                          </th>
                          <th className="px-2 py-1.5 text-center">
                            Local Claims
                          </th>
                          <th className="px-2 py-1.5 text-center">
                            MinIO Raw
                          </th>
                          <th className="px-2 py-1.5 text-center">
                            MinIO Clean
                          </th>
                          <th className="px-2 py-1.5 text-center">In DB</th>
                        </tr>
                      </thead>
                      <tbody>
                        {sync.items.map((item) => (
                          <tr
                            key={item.video_id}
                            className="border-b border-zinc-800/50"
                          >
                            <td className="px-2 py-1.5 font-mono text-zinc-300">
                              {item.video_id}
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.local_raw} />
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.local_clean} />
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.local_claims} />
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.minio_raw} />
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.minio_clean} />
                            </td>
                            <td className="px-2 py-1.5 text-center">
                              <SyncCell present={item.in_db} />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </div>
      </div>

      {/* Tab: Scout Dashboard - recent agent_runs rollups for Scout pipelines. */}
      <div className={activeTab === "scout" ? "" : "hidden"}>
        <ScoutDashboardPanel />
      </div>

      {/* Tab: Channel Coverage — keep mounted to preserve fetched data */}
      <div className={activeTab === "coverage" ? "" : "hidden"}>
        <ChannelCoveragePanel />
      </div>

      {/* Tab: Recon Review — admin-key gated endpoints, mounted only when active. */}
      {activeTab === "recon" && <ReconCandidatesPanel />}

      {/* Tab: Presenters — only mount when active so the channel-coverage
          fetch and the by-channel fetch don't fire on every load. */}
      {activeTab === "presenters" && <PresentersPanel />}

      {/* Tab: Transcript Diff — conditional render so it doesn't fetch
          transcript-test-files on every base change while another tab is
          active. No per-target cache here, so re-fetch on tab re-entry is fine. */}
      {activeTab === "diff" && <TranscriptDiffPanel />}
    </div>
  );
}
