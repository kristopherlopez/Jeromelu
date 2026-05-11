"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { API_BASE, apiFetch } from "@/lib/api";
import type { FacePosition, FaceRun, FaceRunsResponse } from "@/lib/types";
import AssignRunModal from "./AssignRunModal";

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
  const [assigning, setAssigning] = useState<FaceRun | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<FaceRunsResponse>(`/api/sources/${sourceId}/face-runs`);
      setData(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sourceId]);

  useEffect(() => {
    refresh();
  }, [refresh]);

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

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto custom-scrollbar pr-2">
      {data.positions.map((pos) => (
        <PositionSection
          key={pos.position_id}
          position={pos}
          sourceId={sourceId}
          onSeek={onSeek}
          onAssign={setAssigning}
        />
      ))}
      {assigning && (
        <AssignRunModal
          sourceId={sourceId}
          run={assigning}
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

function PositionSection({
  position,
  sourceId,
  onSeek,
  onAssign,
}: {
  position: FacePosition;
  sourceId: string;
  onSeek: (s: number) => void;
  onAssign: (run: FaceRun) => void;
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
      <header className="mb-2 flex items-baseline justify-between">
        <h3 className="text-xs font-semibold uppercase tracking-wider">
          {position.label}
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
      </header>
      <ul className="flex flex-col gap-1">
        {visibleRuns.map((run, idx) => (
          <RunRow
            key={`${position.position_id}-${idx}`}
            run={run}
            sourceId={sourceId}
            onSeek={onSeek}
            onAssign={onAssign}
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
  onAssign,
}: {
  run: FaceRun;
  sourceId: string;
  onSeek: (s: number) => void;
  onAssign: (run: FaceRun) => void;
}) {
  const dur = Math.round(run.end_ts - run.start_ts);
  const canAssign = run.overlapping_turns.length > 0;
  return (
    <li
      className="grid grid-cols-[auto_auto_1fr_auto] items-center gap-2 rounded px-2 py-1.5 text-xs"
      style={{
        borderLeft: `3px solid ${runColor(run)}`,
        backgroundColor: "var(--background-deep)",
      }}
    >
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
              {run.overlapping_turns.length} turn{run.overlapping_turns.length > 1 ? "s" : ""}
            </>
          )}
        </span>
      </button>
      <button
        type="button"
        onClick={() => onAssign(run)}
        disabled={!canAssign}
        className="rounded px-2 py-1 text-[10px] font-medium uppercase tracking-wider"
        style={{
          backgroundColor: canAssign ? "var(--accent)" : "var(--background-deep)",
          color: canAssign ? "#000" : "var(--foreground-ghost)",
          cursor: canAssign ? "pointer" : "not-allowed",
          opacity: canAssign ? 1 : 0.5,
        }}
        title={
          canAssign
            ? `Assign all ${run.overlapping_turns.length} overlapping turn(s) to a Person`
            : "No source_speakers turns overlap this run — nothing to assign"
        }
      >
        Assign
      </button>
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
