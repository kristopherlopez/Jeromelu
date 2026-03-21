"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL!;

// --- Types ---

interface PipelineStages {
  discovered: boolean;
  collected: boolean;
  indexed: boolean;
  cleaned: boolean;
  extracted: boolean;
}

interface PipelineItem {
  source_id: string;
  title: string;
  video_id: string | null;
  published_at: string | null;
  stages: PipelineStages;
  chunk_count: number;
  claim_count: number;
}

interface PipelineResponse {
  summary: { total: number; by_stage: Record<string, number> };
  items: PipelineItem[];
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
const STAGES: StageKey[] = ["discovered", "collected", "indexed", "cleaned", "extracted"];

type SortField = "title" | "published_at" | "stage" | "chunk_count" | "claim_count";
type SortDir = "asc" | "desc";

function getHighestStage(stages: PipelineStages): number {
  for (let i = STAGES.length - 1; i >= 0; i--) {
    if (stages[STAGES[i]]) return i;
  }
  return 0;
}

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

// --- Component ---

export default function AdminClient() {
  const [pipeline, setPipeline] = useState<PipelineResponse | null>(null);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState(false);

  const [sync, setSync] = useState<SyncResponse | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncOpen, setSyncOpen] = useState(false);

  const [stageFilter, setStageFilter] = useState<StageKey | "all">("all");
  const [search, setSearch] = useState("");
  const [sortField, setSortField] = useState<SortField>("published_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const fetchPipeline = useCallback(async () => {
    setPipelineLoading(true);
    setPipelineError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/pipeline`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setPipeline(await res.json());
    } catch (e) {
      setPipelineError(e instanceof Error ? e.message : String(e));
    } finally {
      setPipelineLoading(false);
    }
  }, []);

  const fetchSync = useCallback(async () => {
    setSyncLoading(true);
    setSyncError(null);
    try {
      const res = await fetch(`${API_BASE}/api/admin/sync-status`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setSync(await res.json());
    } catch (e) {
      setSyncError(e instanceof Error ? e.message : String(e));
    } finally {
      setSyncLoading(false);
    }
  }, []);

  // Auto-fetch pipeline on mount
  useEffect(() => {
    fetchPipeline();
  }, [fetchPipeline]);

  const toggleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "title" ? "asc" : "desc");
    }
  };

  // --- Filtered & sorted items ---
  const filteredItems = (pipeline?.items ?? [])
    .filter((item) => {
      if (stageFilter !== "all") {
        let current: StageKey = "discovered";
        for (const s of STAGES) {
          if (item.stages[s]) current = s;
        }
        if (current !== stageFilter) return false;
      }
      if (search) {
        const q = search.toLowerCase();
        if (
          !item.title?.toLowerCase().includes(q) &&
          !item.video_id?.toLowerCase().includes(q)
        )
          return false;
      }
      return true;
    })
    .sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      switch (sortField) {
        case "title":
          return dir * (a.title ?? "").localeCompare(b.title ?? "");
        case "published_at": {
          const ta = a.published_at ? new Date(a.published_at).getTime() : 0;
          const tb = b.published_at ? new Date(b.published_at).getTime() : 0;
          return dir * (ta - tb);
        }
        case "stage":
          return dir * (getHighestStage(a.stages) - getHighestStage(b.stages));
        case "chunk_count":
          return dir * (a.chunk_count - b.chunk_count);
        case "claim_count":
          return dir * (a.claim_count - b.claim_count);
        default:
          return 0;
      }
    });

  return (
    <div className="space-y-8">
      {/* Section 1: Summary Cards */}
      {pipeline && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-5">
          {STAGES.map((stage) => (
            <div
              key={stage}
              className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4 text-center"
            >
              <div className="text-2xl font-bold text-white">
                {pipeline.summary.by_stage[stage] ?? 0}
              </div>
              <div className="mt-1 text-xs font-medium capitalize text-zinc-400">
                {stage}
              </div>
            </div>
          ))}
        </div>
      )}

      {pipelineError && (
        <p className="text-red-400 text-sm">Pipeline error: {pipelineError}</p>
      )}

      {/* Section 2: Pipeline Table */}
      {pipeline && (
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-3">
            <select
              value={stageFilter}
              onChange={(e) => setStageFilter(e.target.value as StageKey | "all")}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white"
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
              placeholder="Search title..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white placeholder:text-zinc-600 focus:border-orange-500 focus:outline-none"
            />
            <button
              onClick={fetchPipeline}
              disabled={pipelineLoading}
              className="ml-auto rounded bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
            >
              {pipelineLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                  <SortHeader field="title" label="Title" current={sortField} dir={sortDir} onSort={toggleSort} />
                  <SortHeader field="published_at" label="Published" current={sortField} dir={sortDir} onSort={toggleSort} />
                  {STAGES.map((s) => (
                    <th key={s} className="px-3 py-2 text-center capitalize">
                      {s.slice(0, 4)}
                    </th>
                  ))}
                  <SortHeader field="chunk_count" label="Chunks" current={sortField} dir={sortDir} onSort={toggleSort} className="text-center" />
                  <SortHeader field="claim_count" label="Claims" current={sortField} dir={sortDir} onSort={toggleSort} className="text-center" />
                </tr>
              </thead>
              <tbody>
                {filteredItems.map((item) => (
                  <tr
                    key={item.source_id}
                    className="border-b border-zinc-800/50 hover:bg-zinc-900/50"
                  >
                    <td className="max-w-xs truncate px-3 py-2 text-white">
                      {item.title}
                    </td>
                    <td className="whitespace-nowrap px-3 py-2 text-zinc-500">
                      {item.published_at
                        ? new Date(item.published_at).toLocaleDateString("en-AU", { day: "2-digit", month: "2-digit", year: "numeric" })
                        : "—"}
                    </td>
                    {STAGES.map((s) => (
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
                {filteredItems.length === 0 && (
                  <tr>
                    <td
                      colSpan={2 + STAGES.length + 2}
                      className="px-3 py-6 text-center text-zinc-600"
                    >
                      No sources match.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-zinc-600">
            {pipeline.summary.total} total sources
          </p>
        </div>
      )}

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
  );
}
