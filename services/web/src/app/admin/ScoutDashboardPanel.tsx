"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAdminApiBase } from "./apiBase";

interface ScoutDashboardWindow {
  limit: number;
  row_count: number;
  pipeline_count: number;
}

interface ScoutPipelineRollup {
  pipeline: string;
  last_run_id: string | null;
  status: string | null;
  started_at: string | null;
  ended_at: string | null;
  summary: string;
  detail: Record<string, unknown>;
  total_cost_usd: number | null;
  run_count: number;
  status_counts: Record<string, number>;
  recent_failure_count: number;
  recent_total_cost_usd: number;
}

interface ScoutDashboardResponse {
  ok: boolean;
  window: ScoutDashboardWindow;
  pipeline_order: string[];
  pipelines: Record<string, ScoutPipelineRollup>;
}

interface DetailEntry {
  key: string;
  value: string;
}

const LIMIT_OPTIONS = [100, 500, 1000, 2000];

function formatDateTime(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-AU", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function formatCurrency(value: number | null | undefined): string {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  const maximumFractionDigits = Math.abs(value) < 1 ? 4 : 2;
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits,
  });
}

function formatScalar(value: unknown): string {
  if (value === null || value === undefined) return "-";
  if (typeof value === "number") {
    return Number.isFinite(value) ? value.toLocaleString() : String(value);
  }
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "string") return value || "-";
  if (Array.isArray(value)) return `${value.length.toLocaleString()} items`;
  if (typeof value === "object") return `${Object.keys(value).length.toLocaleString()} fields`;
  return String(value);
}

function flattenDetail(
  detail: Record<string, unknown>,
  prefix = "",
  depth = 0,
): DetailEntry[] {
  return Object.entries(detail).flatMap(([key, value]) => {
    const label = prefix ? `${prefix}.${key}` : key;
    if (
      value &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      depth < 1
    ) {
      return flattenDetail(value as Record<string, unknown>, label, depth + 1);
    }
    return [{ key: label, value: formatScalar(value) }];
  });
}

function statusClass(status: string | null | undefined): string {
  const normalized = (status ?? "unknown").toLowerCase();
  if (["success", "succeeded", "completed", "ok"].includes(normalized)) {
    return "border-emerald-800 text-emerald-300";
  }
  if (["failed", "aborted", "error"].includes(normalized)) {
    return "border-red-800 text-red-300";
  }
  if (["running", "started", "in_progress"].includes(normalized)) {
    return "border-sky-800 text-sky-300";
  }
  if (["pending", "queued"].includes(normalized)) {
    return "border-amber-800 text-amber-300";
  }
  return "border-zinc-700 text-zinc-400";
}

function StatusBadge({ status }: { status: string | null | undefined }) {
  return (
    <span
      className={`rounded border px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${statusClass(
        status,
      )}`}
    >
      {status ?? "unknown"}
    </span>
  );
}

function statusEntries(counts: Record<string, number>): [string, number][] {
  return Object.entries(counts).sort(
    ([aStatus, aCount], [bStatus, bCount]) =>
      bCount - aCount || aStatus.localeCompare(bStatus),
  );
}

function detailEntries(detail: Record<string, unknown>): DetailEntry[] {
  return flattenDetail(detail)
    .filter((entry) => entry.value !== "-")
    .slice(0, 8);
}

export default function ScoutDashboardPanel() {
  const { base } = useAdminApiBase();
  const [limit, setLimit] = useState(500);
  const cacheKey = `${base}:${limit}`;

  const [cache, setCache] = useState<Map<string, ScoutDashboardResponse>>(
    () => new Map(),
  );
  const data = cache.get(cacheKey) ?? null;
  const fetchedKeys = useRef<Set<string>>(new Set());

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = useCallback(async () => {
    fetchedKeys.current.add(cacheKey);
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      const res = await fetch(
        `${base}/api/admin/scout/dashboard?${params.toString()}`,
      );
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const json = (await res.json()) as ScoutDashboardResponse;
      if (!json.ok) throw new Error("Dashboard response was not ok.");
      setCache((prev) => new Map(prev).set(cacheKey, json));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [base, cacheKey, limit]);

  useEffect(() => {
    if (!fetchedKeys.current.has(cacheKey)) {
      fetchDashboard();
    }
  }, [cacheKey, fetchDashboard]);

  useEffect(() => {
    setError(null);
  }, [base, limit]);

  const orderedPipelines = useMemo(() => {
    if (!data) return [];
    const seen = new Set<string>();
    const ordered = data.pipeline_order
      .map((pipeline) => {
        seen.add(pipeline);
        return data.pipelines[pipeline];
      })
      .filter((pipeline): pipeline is ScoutPipelineRollup => Boolean(pipeline));
    const unordered = Object.values(data.pipelines).filter(
      (pipeline) => !seen.has(pipeline.pipeline),
    );
    return [...ordered, ...unordered];
  }, [data]);

  const recentFailureCount = orderedPipelines.reduce(
    (sum, pipeline) => sum + pipeline.recent_failure_count,
    0,
  );
  const recentTotalCost = orderedPipelines.reduce(
    (sum, pipeline) => sum + pipeline.recent_total_cost_usd,
    0,
  );

  return (
    <div className="rounded-lg border border-zinc-800">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="text-sm font-medium text-zinc-300">Scout Dashboard</span>
        {data && (
          <span className="text-xs text-zinc-500">
            {data.window.pipeline_count.toLocaleString()} pipelines from{" "}
            {data.window.row_count.toLocaleString()} recent runs
          </span>
        )}
        <div className="ml-auto flex flex-wrap items-center gap-2">
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-xs text-white"
            title="Recent agent_runs rows to include"
          >
            {LIMIT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option.toLocaleString()} runs
              </option>
            ))}
          </select>
          <button
            onClick={fetchDashboard}
            disabled={loading}
            className="rounded bg-orange-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-orange-500 disabled:opacity-50"
          >
            {loading
              ? data
                ? "Refreshing..."
                : "Loading..."
              : data
                ? "Refresh"
                : "Load dashboard"}
          </button>
        </div>
      </div>

      {error && (
        <div className="border-t border-zinc-800 px-4 py-3 text-sm text-red-400">
          Error: {error}
        </div>
      )}

      {!data && loading && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          Loading Scout dashboard...
        </div>
      )}

      {!data && !loading && !error && (
        <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
          No dashboard data loaded.
        </div>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-px border-t border-zinc-800 bg-zinc-800 text-xs sm:grid-cols-4">
            <div className="bg-zinc-950 px-4 py-3">
              <div className="text-zinc-600">Window</div>
              <div className="mt-1 font-mono text-zinc-200">
                {data.window.limit.toLocaleString()} rows
              </div>
            </div>
            <div className="bg-zinc-950 px-4 py-3">
              <div className="text-zinc-600">Pipelines</div>
              <div className="mt-1 font-mono text-zinc-200">
                {data.window.pipeline_count.toLocaleString()}
              </div>
            </div>
            <div className="bg-zinc-950 px-4 py-3">
              <div className="text-zinc-600">Recent failures</div>
              <div
                className={`mt-1 font-mono ${
                  recentFailureCount > 0 ? "text-red-300" : "text-zinc-200"
                }`}
              >
                {recentFailureCount.toLocaleString()}
              </div>
            </div>
            <div className="bg-zinc-950 px-4 py-3">
              <div className="text-zinc-600">Recent cost</div>
              <div className="mt-1 font-mono text-zinc-200">
                {formatCurrency(recentTotalCost)}
              </div>
            </div>
          </div>

          {orderedPipelines.length === 0 ? (
            <div className="border-t border-zinc-800 px-4 py-8 text-center text-sm text-zinc-500">
              No Scout pipeline runs in this window.
            </div>
          ) : (
            <div className="overflow-x-auto border-t border-zinc-800">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-zinc-800 text-left text-xs text-zinc-500">
                    <th className="px-3 py-2 text-right">#</th>
                    <th className="px-3 py-2">Pipeline</th>
                    <th className="px-3 py-2">Status</th>
                    <th className="px-3 py-2">Last run</th>
                    <th className="px-3 py-2 text-right">Runs</th>
                    <th className="px-3 py-2 text-right">Failures</th>
                    <th className="px-3 py-2 text-right">Cost</th>
                    <th className="px-3 py-2">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {orderedPipelines.map((pipeline, index) => {
                    const details = detailEntries(pipeline.detail);
                    const lastRunAt = pipeline.ended_at ?? pipeline.started_at;
                    return (
                      <tr
                        key={pipeline.pipeline}
                        className="border-b border-zinc-800/50 align-top hover:bg-zinc-900/50"
                      >
                        <td className="px-3 py-3 text-right font-mono text-xs text-zinc-600">
                          {index + 1}
                        </td>
                        <td className="min-w-[12rem] px-3 py-3">
                          <div className="font-medium text-zinc-100">
                            {pipeline.pipeline}
                          </div>
                          {pipeline.summary && (
                            <div className="mt-1 max-w-xs truncate text-xs text-zinc-500">
                              {pipeline.summary}
                            </div>
                          )}
                        </td>
                        <td className="px-3 py-3">
                          <StatusBadge status={pipeline.status} />
                          {statusEntries(pipeline.status_counts).length > 0 && (
                            <div className="mt-2 flex max-w-[12rem] flex-wrap gap-1">
                              {statusEntries(pipeline.status_counts).map(
                                ([status, count]) => (
                                  <span
                                    key={status}
                                    className="rounded border border-zinc-800 px-1.5 py-0.5 text-[10px] text-zinc-500"
                                  >
                                    {status} {count.toLocaleString()}
                                  </span>
                                ),
                              )}
                            </div>
                          )}
                        </td>
                        <td className="whitespace-nowrap px-3 py-3">
                          <div className="text-zinc-300">
                            {formatDateTime(lastRunAt)}
                          </div>
                          <div className="mt-1 max-w-[10rem] truncate font-mono text-[11px] text-zinc-600">
                            {pipeline.last_run_id ?? "-"}
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right font-mono text-zinc-300">
                          {pipeline.run_count.toLocaleString()}
                        </td>
                        <td
                          className={`px-3 py-3 text-right font-mono ${
                            pipeline.recent_failure_count > 0
                              ? "text-red-300"
                              : "text-zinc-500"
                          }`}
                        >
                          {pipeline.recent_failure_count.toLocaleString()}
                        </td>
                        <td className="whitespace-nowrap px-3 py-3 text-right">
                          <div className="font-mono text-zinc-300">
                            {formatCurrency(pipeline.recent_total_cost_usd)}
                          </div>
                          <div className="mt-1 text-[11px] text-zinc-600">
                            last {formatCurrency(pipeline.total_cost_usd)}
                          </div>
                        </td>
                        <td className="min-w-[20rem] px-3 py-3">
                          {details.length === 0 ? (
                            <span className="text-xs text-zinc-600">
                              No detail fields.
                            </span>
                          ) : (
                            <div className="grid gap-1 sm:grid-cols-2">
                              {details.map((entry) => (
                                <div
                                  key={`${pipeline.pipeline}-${entry.key}`}
                                  className="min-w-0 rounded border border-zinc-900 bg-zinc-950 px-2 py-1"
                                >
                                  <div className="truncate text-[10px] text-zinc-600">
                                    {entry.key}
                                  </div>
                                  <div className="truncate font-mono text-[11px] text-zinc-300">
                                    {entry.value}
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
