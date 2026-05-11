"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { API_BASE, apiFetch } from "@/lib/api";
import type {
  FaceClusterKind,
  FacePosition,
  FaceRun,
  FaceRunOverlapTurn,
  FaceRunsResponse,
} from "@/lib/types";
import AssignRunModal from "./AssignRunModal";

/** Derived view over a FacePosition for the cluster-level Assign action.
 *  Captures the union of overlapping turns across all the cluster's runs,
 *  the deduped count, current dominant attribution, and the time range. */
interface ClusterSelection {
  clusterId: number | null;
  clusterLabel: string;
  segments: FaceRunOverlapTurn[];
  totalDetections: number;
  currentPersonName: string | null;
  firstTs: number;
  lastTs: number;
}

function clusterSelectionFrom(pos: FacePosition): ClusterSelection {
  // Dedupe overlapping_turns by segment_id across all of the cluster's runs.
  const segMap = new Map<string, FaceRunOverlapTurn>();
  for (const run of pos.runs) {
    for (const t of run.overlapping_turns) {
      segMap.set(t.segment_id, t);
    }
  }
  const segments = Array.from(segMap.values()).sort(
    (a, b) => a.start_ts - b.start_ts,
  );

  // Most-frequent speaker_person_name across the cluster's segments —
  // approximation of "currently attributed to" for header display.
  const nameCounts = new Map<string, number>();
  for (const t of segments) {
    if (t.speaker_person_name) {
      nameCounts.set(
        t.speaker_person_name,
        (nameCounts.get(t.speaker_person_name) || 0) + 1,
      );
    }
  }
  let currentPersonName: string | null = null;
  let topCount = 0;
  for (const [name, count] of nameCounts) {
    if (count > topCount) {
      currentPersonName = name;
      topCount = count;
    }
  }

  const firstTs = pos.runs.length
    ? Math.min(...pos.runs.map((r) => r.start_ts))
    : 0;
  const lastTs = pos.runs.length
    ? Math.max(...pos.runs.map((r) => r.end_ts))
    : 0;

  return {
    clusterId: pos.cluster_id ?? null,
    clusterLabel: pos.label,
    segments,
    totalDetections: pos.detection_count,
    currentPersonName,
    firstTs,
    lastTs,
  };
}

// Top-N runs (by frame_count) rendered per section on initial load.
// Multi-cam shows can produce 80-100 runs per cluster; rendering all
// at once fires hundreds of face-crop requests in parallel and
// saturates the worker. The operator can click "Show all" to expand.
const RUNS_INITIAL_LIMIT = 20;

interface Props {
  sourceId: string;
  /** Seek the video preview when an operator clicks a row. */
  onSeek: (seconds: number) => void;
}

function fmtTs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function pct(n: number | null): string {
  if (n === null) return "—";
  return `${Math.round(n * 100)}%`;
}

function runLabel(run: FaceRun): string {
  return run.person_name ?? "?";
}

function runColor(run: FaceRun): string {
  return run.person_id === null ? "var(--foreground-ghost)" : "var(--accent)";
}

export default function FacesPanel({ sourceId, onSeek }: Props) {
  const [data, setData] = useState<FaceRunsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // The cluster currently being assigned to a Person. Cluster-level,
  // not run-level — a single Assign covers all detections in the
  // cluster. Runs get a Move action instead (re-cluster a stretch).
  const [assigning, setAssigning] = useState<ClusterSelection | null>(null);
  const [showExcluded, setShowExcluded] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<FaceRunsResponse>(
        `/api/sources/${sourceId}/face-runs?include_excluded=${showExcluded}`,
      );
      setData(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sourceId, showExcluded]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Move one run's detections to a different cluster. Used by the
  // per-row Move popover when a stretch of frames was mis-clustered
  // (HDBSCAN occasionally groups a profile shot of host A with
  // host B's cluster because the angle made the embedding closer).
  const moveRun = useCallback(
    async (
      sourceClusterId: number,
      targetClusterId: number,
      startTs: number,
      endTs: number,
    ) => {
      try {
        const resp = await fetch(
          `${API_BASE}/api/sources/${sourceId}/face-runs/move-run`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              source_cluster_id: sourceClusterId,
              target_cluster_id: targetClusterId,
              start_ts: startTs,
              end_ts: endTs,
            }),
          },
        );
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(`API ${resp.status}: ${text}`);
        }
        refresh();
      } catch (e) {
        setError(String(e));
      }
    },
    [sourceId, refresh],
  );

  // Toggle the kind of one cluster — used by the Exclude/Include
  // button on each section header.
  const overrideCluster = useCallback(
    async (
      clusterId: number,
      patch: { excluded?: boolean; kind?: FaceClusterKind },
    ) => {
      try {
        const resp = await fetch(
          `${API_BASE}/api/sources/${sourceId}/face-clusters/${clusterId}`,
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(patch),
          },
        );
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(`API ${resp.status}: ${text}`);
        }
        refresh();
      } catch (e) {
        setError(String(e));
      }
    },
    [sourceId, refresh],
  );

  if (loading) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Loading face runs…
      </div>
    );
  }
  if (error) {
    return (
      <div className="text-xs" style={{ color: "#f87171" }}>
        Failed to load: {error}
      </div>
    );
  }
  if (!data || data.positions.length === 0) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        No face runs for this source — face-track JSON is empty or missing.
      </div>
    );
  }

  const hiddenCount = data.excluded_count ?? 0;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto custom-scrollbar pr-2">
      {(hiddenCount > 0 || showExcluded) && (
        <div
          className="flex items-center justify-between rounded border px-3 py-1.5 text-xs"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--background-deep)",
            color: "var(--foreground-secondary)",
          }}
        >
          <span>
            {showExcluded
              ? `Showing excluded clusters too`
              : `${hiddenCount} cluster${hiddenCount === 1 ? "" : "s"} hidden as portraits / noise`}
          </span>
          <button
            type="button"
            onClick={() => setShowExcluded((v) => !v)}
            className="rounded border px-2 py-0.5 text-[10px] uppercase tracking-wider"
            style={{ borderColor: "var(--border)" }}
          >
            {showExcluded ? "Hide excluded" : "Show excluded"}
          </button>
        </div>
      )}
      {data.positions.map((pos) => (
        <PositionSection
          key={pos.position_id}
          position={pos}
          sourceId={sourceId}
          onSeek={onSeek}
          onAssign={() => setAssigning(clusterSelectionFrom(pos))}
          onOverride={overrideCluster}
          onMoveRun={moveRun}
          allClusters={data.positions
            .filter((p) => p.cluster_id !== null && p.cluster_id !== undefined)
            .map((p) => ({
              clusterId: p.cluster_id as number,
              label: p.label,
            }))}
        />
      ))}
      {assigning && (
        <AssignRunModal
          sourceId={sourceId}
          clusterId={assigning.clusterId}
          clusterLabel={assigning.clusterLabel}
          segments={assigning.segments}
          totalDetections={assigning.totalDetections}
          currentPersonName={assigning.currentPersonName}
          firstTs={assigning.firstTs}
          lastTs={assigning.lastTs}
          onClose={() => setAssigning(null)}
          onSaved={() => {
            setAssigning(null);
            // Refresh so the row's person_name updates and the
            // overlapping_turns reflect their new attribution.
            refresh();
          }}
        />
      )}
    </div>
  );
}

function kindBadge(
  kind: FaceClusterKind | undefined,
  detectedKind: FaceClusterKind | undefined,
): { text: string; color: string } | null {
  const effective = kind ?? detectedKind;
  if (!effective) return null;
  switch (effective) {
    case "portrait":
      return { text: "Portrait", color: "#9ca3af" }; // grey-400
    case "noise":
      return { text: "Noise", color: "#9ca3af" };
    case "person":
      return { text: "Person", color: "var(--accent)" };
  }
}

function PositionSection({
  position,
  sourceId,
  onSeek,
  onAssign,
  onOverride,
  onMoveRun,
  allClusters,
}: {
  position: FacePosition;
  sourceId: string;
  onSeek: (s: number) => void;
  onAssign: () => void;
  onOverride: (
    clusterId: number,
    patch: { excluded?: boolean; kind?: FaceClusterKind },
  ) => void;
  onMoveRun: (
    sourceClusterId: number,
    targetClusterId: number,
    startTs: number,
    endTs: number,
  ) => void;
  allClusters: { clusterId: number; label: string }[];
}) {
  // Sort runs by frame_count desc so the top entries are the most
  // screen-time-relevant — usually what the operator cares about for
  // triage. Stable across renders via useMemo on identity.
  const sortedRuns = useMemo(
    () => [...position.runs].sort((a, b) => b.frame_count - a.frame_count),
    [position.runs],
  );
  const [expanded, setExpanded] = useState(false);
  const visibleRuns =
    expanded || sortedRuns.length <= RUNS_INITIAL_LIMIT
      ? sortedRuns
      : sortedRuns.slice(0, RUNS_INITIAL_LIMIT);
  const hiddenCount = sortedRuns.length - visibleRuns.length;

  return (
    <section
      className="rounded border p-3"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--surface)" }}
    >
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider">
          {position.label}
          {(() => {
            const badge = kindBadge(position.kind, position.detected_kind);
            if (!badge) return null;
            const isOverride =
              position.kind != null && position.kind !== position.detected_kind;
            return (
              <span
                className="ml-2 rounded border px-1.5 py-0.5 text-[9px] font-normal uppercase tracking-wider"
                style={{
                  borderColor: badge.color,
                  color: badge.color,
                }}
                title={
                  isOverride
                    ? `Operator override (detected: ${position.detected_kind ?? "—"})`
                    : `Auto-detected`
                }
              >
                {badge.text}
                {isOverride ? "*" : ""}
              </span>
            );
          })()}
          <span
            className="ml-2 font-normal normal-case"
            style={{ color: "var(--foreground-ghost)" }}
          >
            {position.detection_count.toLocaleString()} detections ·{" "}
            {position.runs.length} runs
            {hiddenCount > 0 && (
              <span className="ml-1">
                (showing top {visibleRuns.length})
              </span>
            )}
          </span>
        </h3>
        <div className="flex shrink-0 items-center gap-2">
          {/* Cluster-level assign — one click attributes every detection
              in the cluster to a Person. Disabled for the Outliers
              bucket (cluster_id=null) since it has no embeddings to
              copy as exemplars and represents HDBSCAN noise. */}
          {position.cluster_id !== null &&
            position.cluster_id !== undefined &&
            !position.excluded && (
              <button
                type="button"
                onClick={onAssign}
                className="rounded px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider whitespace-nowrap"
                style={{
                  backgroundColor: "var(--accent)",
                  color: "#000",
                }}
                title="Assign every detection in this cluster to a Person"
              >
                Assign
              </button>
            )}
          {position.cluster_id !== null && position.cluster_id !== undefined && (
            <button
              type="button"
              onClick={() => {
                const nowExcluded = !position.excluded;
                onOverride(position.cluster_id as number, {
                  excluded: nowExcluded,
                  // If hiding a real-person mistake, set kind=portrait
                  // so the auto-tag doesn't re-include on next analyse.
                  ...(nowExcluded ? { kind: "portrait" as const } : {}),
                });
              }}
              className="rounded border px-2 py-0.5 text-[10px] uppercase tracking-wider whitespace-nowrap"
              style={{
                borderColor: "var(--border)",
                color: "var(--foreground-secondary)",
              }}
              title={
                position.excluded
                  ? "Include this cluster in the default runs view"
                  : "Exclude this cluster (mark as portrait / not a real person)"
              }
            >
              {position.excluded ? "Include" : "Exclude"}
            </button>
          )}
        </div>
      </header>
      <ul className="flex flex-col gap-1">
        {visibleRuns.map((run, idx) => (
          <RunRow
            key={`${position.position_id}-${idx}`}
            run={run}
            sourceId={sourceId}
            onSeek={onSeek}
            currentClusterId={position.cluster_id ?? null}
            otherClusters={allClusters.filter(
              (c) => c.clusterId !== position.cluster_id,
            )}
            onMove={(target) =>
              onMoveRun(
                position.cluster_id as number,
                target,
                run.start_ts,
                run.end_ts,
              )
            }
          />
        ))}
      </ul>
      {hiddenCount > 0 && (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="mt-2 w-full rounded border px-3 py-1.5 text-xs"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-secondary)",
            backgroundColor: "var(--background-deep)",
          }}
        >
          Show {hiddenCount} more {hiddenCount === 1 ? "run" : "runs"}
        </button>
      )}
    </section>
  );
}

function RunRow({
  run,
  sourceId,
  onSeek,
  currentClusterId,
  otherClusters,
  onMove,
}: {
  run: FaceRun;
  sourceId: string;
  onSeek: (s: number) => void;
  /** null = Outliers bucket; Move action disabled there. */
  currentClusterId: number | null;
  /** Available targets (all other clusters in this source). */
  otherClusters: { clusterId: number; label: string }[];
  onMove: (targetClusterId: number) => void;
}) {
  const dur = Math.round(run.end_ts - run.start_ts);
  const canMove = currentClusterId !== null && otherClusters.length > 0;
  const [pickerOpen, setPickerOpen] = useState(false);

  return (
    <li
      className="rounded px-2 py-1.5 text-xs"
      style={{
        borderLeft: `3px solid ${runColor(run)}`,
        backgroundColor: "var(--background-deep)",
      }}
    >
      <div className="grid grid-cols-[auto_auto_1fr_auto] items-center gap-2">
        <FaceThumb
          sourceId={sourceId}
          ts={run.start_sample.ts}
          bbox={run.start_sample.bbox}
        />
        <FaceThumb
          sourceId={sourceId}
          ts={run.end_sample.ts}
          bbox={run.end_sample.bbox}
        />
        <button
          type="button"
          className="flex flex-col items-start text-left"
          onClick={() => onSeek(run.start_ts)}
          title="Seek video to start"
        >
          <span style={{ color: runColor(run) }}>
            <strong>{runLabel(run)}</strong>
            {run.avg_similarity !== null && (
              <span className="ml-1.5 font-normal" style={{ color: "var(--foreground-ghost)" }}>
                sim {pct(run.avg_similarity)}
              </span>
            )}
          </span>
          <span style={{ color: "var(--foreground-ghost)" }}>
            {fmtTs(run.start_ts)} – {fmtTs(run.end_ts)}
            {" · "}
            {dur}s
            {" · "}
            {run.frame_count} frames
            {run.overlapping_turns.length > 0 && (
              <>
                {" · "}
                {run.overlapping_turns.length} turn
                {run.overlapping_turns.length > 1 ? "s" : ""}
              </>
            )}
          </span>
        </button>
        <button
          type="button"
          onClick={() => setPickerOpen((v) => !v)}
          disabled={!canMove}
          className="rounded border px-2 py-1 text-[10px] font-medium uppercase tracking-wider"
          style={{
            borderColor: canMove ? "var(--border)" : "var(--background-deep)",
            color: canMove ? "var(--foreground-secondary)" : "var(--foreground-ghost)",
            cursor: canMove ? "pointer" : "not-allowed",
            opacity: canMove ? 1 : 0.5,
            backgroundColor: pickerOpen ? "var(--surface)" : "transparent",
          }}
          title={
            canMove
              ? "Move this run's detections into a different cluster (re-cluster a mis-grouped stretch)"
              : "Outliers / single-cluster source — nothing to move to"
          }
        >
          {pickerOpen ? "Cancel" : "Move →"}
        </button>
      </div>
      {pickerOpen && canMove && (
        <div
          className="mt-2 flex flex-wrap gap-1.5 rounded border px-2 py-1.5"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--surface)",
          }}
        >
          <span
            className="self-center text-[10px] uppercase tracking-wider"
            style={{ color: "var(--foreground-ghost)" }}
          >
            Move to:
          </span>
          {otherClusters.map((c) => (
            <button
              key={c.clusterId}
              type="button"
              onClick={() => {
                setPickerOpen(false);
                onMove(c.clusterId);
              }}
              className="rounded border px-2 py-0.5 text-[10px]"
              style={{
                borderColor: "var(--border)",
                color: "var(--foreground-secondary)",
                backgroundColor: "var(--background-deep)",
              }}
            >
              → {c.label}
            </button>
          ))}
        </div>
      )}
    </li>
  );
}

function FaceThumb({
  sourceId,
  ts,
  bbox,
}: {
  sourceId: string;
  ts: number;
  bbox: [number, number, number, number];
}) {
  const bboxParam = bbox.map((n) => n.toFixed(3)).join(",");
  const url = `${API_BASE}/api/sources/${sourceId}/face-crop?ts=${ts}&bbox=${encodeURIComponent(bboxParam)}`;
  return (
    <div
      className="overflow-hidden rounded border"
      style={{
        borderColor: "var(--border)",
        width: 36,
        height: 36,
      }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={url}
        alt={`face at ${fmtTs(ts)}`}
        loading="lazy"
        className="h-full w-full object-cover"
      />
    </div>
  );
}
