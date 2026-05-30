"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { useAdminApiBase } from "./apiBase";

type CandidateKind = "channel" | "video";
type KindFilter = "all" | CandidateKind;

interface ReconCandidate {
  id: string;
  kind: CandidateKind;
  platform: string;
  external_id: string;
  url: string;
  title: string;
  description: string | null;
  channel_external_id: string | null;
  content_categories: string[];
  score: number | null;
  score_reasons: unknown[];
  discovered_via: string;
  discovered_at: string;
  status: string;
  run_id: string | null;
}

interface ReconCandidateDetail extends ReconCandidate {
  metadata_json: Record<string, unknown> | null;
  reviewed_at: string | null;
  reviewed_by: string | null;
  reviewed_note: string | null;
  promoted_channel_id: string | null;
}

interface ReconCandidatesResponse {
  count: number;
  candidates: ReconCandidate[];
}

interface ReconStatsResponse {
  by_status: Record<string, Record<string, number>>;
}

const STORAGE_KEY = "admin.reconKey";
const REVIEWED_BY = "admin-ui";

function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatNumber(value: number | null | undefined): string {
  return typeof value === "number" ? value.toLocaleString() : "-";
}

function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function scoreClass(score: number | null): string {
  if (score === null) return "text-zinc-600";
  if (score >= 0.8) return "text-emerald-400";
  if (score >= 0.55) return "text-amber-400";
  return "text-zinc-400";
}

function kindBadgeClass(kind: CandidateKind): string {
  return kind === "channel"
    ? "border-sky-800 text-sky-300"
    : "border-violet-800 text-violet-300";
}

function scoreReasons(reasons: unknown[]): string[] {
  return reasons
    .map((reason) => formatMetadataValue(reason))
    .filter((reason) => reason !== "-");
}

async function fetchJson<T>(
  url: string,
  options: RequestInit,
  emptyMessage = "Request failed",
): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    if (res.status === 403) throw new Error("Invalid admin key.");
    if (res.status === 422) throw new Error("Admin key is required.");
    throw new Error(`${emptyMessage}: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

export default function ReconCandidatesPanel() {
  const { base } = useAdminApiBase();

  const [keyInput, setKeyInput] = useState("");
  const [adminKey, setAdminKey] = useState("");
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");
  const [minScore, setMinScore] = useState("");

  const [candidates, setCandidates] = useState<ReconCandidate[]>([]);
  const [stats, setStats] = useState<ReconStatsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [detailsById, setDetailsById] = useState<Map<string, ReconCandidateDetail>>(
    () => new Map(),
  );
  const [detailLoadingId, setDetailLoadingId] = useState<string | null>(null);

  const [actionId, setActionId] = useState<string | null>(null);
  const [notesById, setNotesById] = useState<Record<string, string>>({});

  useEffect(() => {
    const stored = window.sessionStorage.getItem(STORAGE_KEY) ?? "";
    setKeyInput(stored);
    setAdminKey(stored);
  }, []);

  const headers = useCallback(
    (json = false): HeadersInit => {
      const h: Record<string, string> = {
        "X-Admin-Key": adminKey.trim(),
      };
      if (json) h["Content-Type"] = "application/json";
      return h;
    },
    [adminKey],
  );

  const refreshCandidates = useCallback(async () => {
    const key = adminKey.trim();
    if (!key) {
      setCandidates([]);
      setStats(null);
      setError(null);
      return;
    }

    const params = new URLSearchParams({
      status: "pending",
      limit: "100",
    });
    if (kindFilter !== "all") params.set("kind", kindFilter);
    if (minScore.trim()) params.set("min_score", minScore.trim());

    setLoading(true);
    setError(null);
    try {
      const [listData, statsData] = await Promise.all([
        fetchJson<ReconCandidatesResponse>(
          `${base}/api/admin/recon/candidates?${params.toString()}`,
          { headers: headers() },
          "Failed to load candidates",
        ),
        fetchJson<ReconStatsResponse>(
          `${base}/api/admin/recon/stats`,
          { headers: headers() },
          "Failed to load stats",
        ),
      ]);
      setCandidates(listData.candidates ?? []);
      setStats(statsData);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [adminKey, base, headers, kindFilter, minScore]);

  useEffect(() => {
    refreshCandidates();
  }, [refreshCandidates]);

  const saveAdminKey = () => {
    const next = keyInput.trim();
    if (next) {
      window.sessionStorage.setItem(STORAGE_KEY, next);
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY);
    }
    setAdminKey(next);
  };

  const clearAdminKey = () => {
    window.sessionStorage.removeItem(STORAGE_KEY);
    setKeyInput("");
    setAdminKey("");
    setCandidates([]);
    setStats(null);
    setError(null);
  };

  const toggleDetails = async (candidateId: string) => {
    if (expandedId === candidateId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(candidateId);
    if (detailsById.has(candidateId)) return;

    setDetailLoadingId(candidateId);
    setError(null);
    try {
      const detail = await fetchJson<ReconCandidateDetail>(
        `${base}/api/admin/recon/candidates/${candidateId}`,
        { headers: headers() },
        "Failed to load metadata",
      );
      setDetailsById((prev) => new Map(prev).set(candidateId, detail));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDetailLoadingId(null);
    }
  };

  const reviewCandidate = useCallback(
    async (candidateId: string, action: "approve" | "reject") => {
      const key = adminKey.trim();
      if (!key) {
        setError("Admin key is required.");
        return;
      }
      setActionId(candidateId);
      setError(null);
      try {
        const note = notesById[candidateId]?.trim();
        await fetchJson(
          `${base}/api/admin/recon/candidates/${candidateId}/${action}`,
          {
            method: "POST",
            headers: headers(true),
            body: JSON.stringify({ reviewed_by: REVIEWED_BY, note: note || undefined }),
          },
          `Failed to ${action} candidate`,
        );
        setExpandedId(null);
        setDetailsById((prev) => {
          const next = new Map(prev);
          next.delete(candidateId);
          return next;
        });
        setNotesById((prev) => {
          const next = { ...prev };
          delete next[candidateId];
          return next;
        });
        await refreshCandidates();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setActionId(null);
      }
    },
    [adminKey, base, headers, notesById, refreshCandidates],
  );

  const statsSummary = useMemo(() => {
    const byStatus = stats?.by_status ?? {};
    const pending = byStatus.pending ?? {};
    const approved = byStatus.approved ?? {};
    const rejected = byStatus.rejected ?? {};
    return {
      pending: Object.values(pending).reduce((sum, n) => sum + n, 0),
      approved: Object.values(approved).reduce((sum, n) => sum + n, 0),
      rejected: Object.values(rejected).reduce((sum, n) => sum + n, 0),
      pendingChannels: pending.channel ?? 0,
      pendingVideos: pending.video ?? 0,
    };
  }, [stats]);

  return (
    <div className="rounded-lg border border-zinc-800">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="text-sm font-medium text-zinc-300">Recon Candidates</span>
        {stats && (
          <div className="flex flex-wrap gap-3 text-xs text-zinc-500">
            <span>
              {statsSummary.pending.toLocaleString()} pending
              <span className="text-zinc-600">
                {" "}
                ({statsSummary.pendingChannels.toLocaleString()} channels,{" "}
                {statsSummary.pendingVideos.toLocaleString()} videos)
              </span>
            </span>
            <span>{statsSummary.approved.toLocaleString()} approved</span>
            <span>{statsSummary.rejected.toLocaleString()} rejected</span>
          </div>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <input
            type="password"
            value={keyInput}
            onChange={(e) => setKeyInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") saveAdminKey();
            }}
            placeholder="Admin key"
            className="w-40 rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-white placeholder:text-zinc-600 focus:border-orange-500 focus:outline-none"
          />
          <button
            onClick={saveAdminKey}
            className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-800"
          >
            Use Key
          </button>
          {adminKey && (
            <button
              onClick={clearAdminKey}
              className="rounded border border-zinc-800 bg-zinc-950 px-3 py-1.5 text-xs font-semibold text-zinc-500 hover:text-zinc-300"
            >
              Clear
            </button>
          )}
          <button
            onClick={refreshCandidates}
            disabled={!adminKey.trim() || loading}
            className="rounded bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
          >
            {loading ? "Loading..." : "Refresh"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 border-t border-zinc-800 px-4 py-3">
        <select
          value={kindFilter}
          onChange={(e) => setKindFilter(e.target.value as KindFilter)}
          className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white"
        >
          <option value="all">All kinds</option>
          <option value="channel">Channels</option>
          <option value="video">Videos</option>
        </select>
        <input
          inputMode="decimal"
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
          placeholder="Min score"
          className="w-28 rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-sm text-white placeholder:text-zinc-600 focus:border-orange-500 focus:outline-none"
        />
        <span className="text-xs text-zinc-500">
          Showing pending candidates from {base}
        </span>
      </div>

      {error && (
        <div className="border-t border-zinc-800 px-4 py-3 text-sm text-red-400">
          Error: {error}
        </div>
      )}

      {!adminKey.trim() && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          Admin key required for Recon review.
        </div>
      )}

      {adminKey.trim() && loading && candidates.length === 0 && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          Loading pending candidates...
        </div>
      )}

      {adminKey.trim() && !loading && candidates.length === 0 && !error && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          No pending Recon candidates match.
        </div>
      )}

      {candidates.length > 0 && (
        <div className="divide-y divide-zinc-800 border-t border-zinc-800">
          {candidates.map((candidate) => {
            const reasons = scoreReasons(candidate.score_reasons);
            const detail = detailsById.get(candidate.id);
            const metadata = detail?.metadata_json ?? null;
            const metadataEntries = metadata ? Object.entries(metadata) : [];
            const actionPending = actionId === candidate.id;
            return (
              <div key={candidate.id} className="px-4 py-4 hover:bg-zinc-900/30">
                <div className="flex flex-wrap items-start gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <a
                        href={candidate.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="min-w-0 truncate text-base font-medium text-orange-400 hover:text-orange-300 hover:underline"
                      >
                        {candidate.title}
                      </a>
                      <span
                        className={`rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${kindBadgeClass(candidate.kind)}`}
                      >
                        {candidate.kind}
                      </span>
                      <span className={`font-mono text-xs ${scoreClass(candidate.score)}`}>
                        {candidate.score === null ? "-" : candidate.score.toFixed(2)}
                      </span>
                    </div>
                    {candidate.description && (
                      <p className="mt-1 max-w-4xl text-sm leading-6 text-zinc-400">
                        {candidate.description}
                      </p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-500">
                      <span>{candidate.platform}</span>
                      <span className="font-mono">{candidate.external_id}</span>
                      {candidate.channel_external_id && (
                        <span className="font-mono">channel {candidate.channel_external_id}</span>
                      )}
                      <span>{formatDateTime(candidate.discovered_at)}</span>
                      <span>{candidate.discovered_via}</span>
                      {candidate.run_id && <span className="font-mono">run {candidate.run_id}</span>}
                    </div>
                  </div>

                  <div className="flex shrink-0 flex-wrap gap-2">
                    <button
                      onClick={() => toggleDetails(candidate.id)}
                      disabled={detailLoadingId === candidate.id}
                      className="rounded border border-zinc-700 bg-zinc-900 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-800 disabled:opacity-50"
                    >
                      {expandedId === candidate.id ? "Hide Metadata" : "Metadata"}
                    </button>
                    <button
                      onClick={() => reviewCandidate(candidate.id, "approve")}
                      disabled={actionId !== null}
                      className="rounded bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
                    >
                      {actionPending ? "Approving..." : "Approve"}
                    </button>
                    <button
                      onClick={() => reviewCandidate(candidate.id, "reject")}
                      disabled={actionId !== null}
                      className="rounded bg-zinc-800 px-3 py-1.5 text-xs font-semibold text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
                    >
                      {actionPending ? "Rejecting..." : "Reject"}
                    </button>
                  </div>
                </div>

                <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_18rem]">
                  <div>
                    {candidate.content_categories.length > 0 && (
                      <div className="mb-2 flex flex-wrap gap-1.5">
                        {candidate.content_categories.map((category) => (
                          <span
                            key={category}
                            className="rounded border border-zinc-800 bg-zinc-900 px-2 py-0.5 text-[10px] uppercase tracking-wider text-zinc-400"
                          >
                            {category}
                          </span>
                        ))}
                      </div>
                    )}
                    {reasons.length > 0 ? (
                      <ul className="space-y-1 text-sm text-zinc-300">
                        {reasons.map((reason, index) => (
                          <li key={`${candidate.id}-${index}`} className="flex gap-2">
                            <span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-orange-500" />
                            <span>{reason}</span>
                          </li>
                        ))}
                      </ul>
                    ) : (
                      <p className="text-sm text-zinc-600">No score reasons supplied.</p>
                    )}
                  </div>
                  <textarea
                    value={notesById[candidate.id] ?? ""}
                    onChange={(e) =>
                      setNotesById((prev) => ({
                        ...prev,
                        [candidate.id]: e.target.value,
                      }))
                    }
                    placeholder="Review note"
                    className="min-h-20 rounded border border-zinc-800 bg-zinc-950 px-3 py-2 text-xs text-zinc-300 placeholder:text-zinc-600 focus:border-orange-500 focus:outline-none"
                  />
                </div>

                {expandedId === candidate.id && (
                  <div className="mt-4 rounded border border-zinc-800 bg-zinc-950/60">
                    {detailLoadingId === candidate.id && (
                      <div className="px-3 py-4 text-center text-sm text-zinc-500">
                        Loading metadata...
                      </div>
                    )}
                    {detail && (
                      <>
                        <div className="grid gap-2 border-b border-zinc-800 px-3 py-3 text-xs text-zinc-500 sm:grid-cols-2 lg:grid-cols-4">
                          <div>
                            <span className="text-zinc-600">Reviewed</span>
                            <div>{formatDateTime(detail.reviewed_at)}</div>
                          </div>
                          <div>
                            <span className="text-zinc-600">Reviewed by</span>
                            <div>{detail.reviewed_by ?? "-"}</div>
                          </div>
                          <div>
                            <span className="text-zinc-600">Promoted channel</span>
                            <div className="font-mono">{detail.promoted_channel_id ?? "-"}</div>
                          </div>
                          <div>
                            <span className="text-zinc-600">Status</span>
                            <div>{detail.status}</div>
                          </div>
                        </div>
                        {metadataEntries.length === 0 ? (
                          <div className="px-3 py-4 text-sm text-zinc-600">No metadata.</div>
                        ) : (
                          <div className="grid gap-2 px-3 py-3 text-xs sm:grid-cols-2 lg:grid-cols-3">
                            {metadataEntries.map(([key, value]) => (
                              <div key={key} className="min-w-0 rounded border border-zinc-900 bg-zinc-950 p-2">
                                <div className="text-zinc-600">{key}</div>
                                <div className="break-words font-mono text-zinc-300">
                                  {key === "subscribers" || key === "video_count" || key === "view_count"
                                    ? formatNumber(typeof value === "number" ? value : null)
                                    : formatMetadataValue(value)}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        {detail.reviewed_note && (
                          <div className="border-t border-zinc-800 px-3 py-3 text-xs text-zinc-400">
                            {detail.reviewed_note}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
