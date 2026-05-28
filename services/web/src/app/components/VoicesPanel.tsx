"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch, apiPost } from "@/lib/api";
import type {
  VoiceCluster,
  VoiceClusterTurn,
  VoiceClustersResponse,
} from "@/lib/types";
import AssignVoiceModal from "./AssignVoiceModal";

interface Props {
  sourceId: string;
  /** Seek the YouTube/video preview when an operator clicks a sample turn. */
  onSeek: (seconds: number) => void;
  /** Called after a cluster assign succeeds so the parent can re-fetch
   *  source detail (speakers list drives the overlay match-method colour). */
  onClusterAssigned?: () => void;
}

// Turns per cluster rendered before the operator hits "Show all". Hosts on
// long podcasts can rack up 400+ turns per cluster; rendering them all by
// default works but slows interactive scrolling. 50 covers the common
// review case and the expand is one click.
const TURNS_INITIAL_LIMIT = 50;

function fmtTs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

function fmtTurnDuration(seconds: number): string {
  // Tight format for the per-row badge — most turns are 1-30s.
  if (seconds < 1) return `${seconds.toFixed(1)}s`;
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}m${s ? ` ${s}s` : ""}`;
}

function pct(n: number | null): string {
  if (n === null) return "—";
  return `${Math.round(n * 100)}%`;
}

// Match-method colours — same mapping as the YouTube overlay so the
// Voices tab reads consistently with the face boxes drawn over the
// player. See speaker-identification.md § Concepts → Match method.
function methodColor(method: string | null): string {
  switch (method) {
    case "voice+face":
      return "#4ade80"; // green
    case "voice":
      return "#60a5fa"; // blue
    case "face":
      return "#fbbf24"; // amber
    case "manual":
      return "#c084fc"; // purple
    default:
      return "var(--foreground-ghost)";
  }
}

interface ReclusterResponse {
  source_id: string;
  n_turns_total: number;
  n_turns_with_embedding: number;
  n_clusters: number;
  n_noise: number;
  cluster_sizes: number[];
  params_used: {
    min_cluster_size: number;
    min_samples: number;
    noise_threshold: number;
  };
}

export default function VoicesPanel({
  sourceId,
  onSeek,
  onClusterAssigned,
}: Props) {
  const [data, setData] = useState<VoiceClustersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState<VoiceCluster | null>(null);

  // HDBSCAN re-cluster controls. Defaults mirror VoiceClusterParams on
  // the API side — kept loose enough for typical commentary podcasts but
  // tunable per-source from this header without redeploying.
  const [minClusterSize, setMinClusterSize] = useState(5);
  const [minSamples, setMinSamples] = useState(2);
  const [noiseThreshold, setNoiseThreshold] = useState(0.25);
  const [reclustering, setReclustering] = useState(false);
  const [reclusterStatus, setReclusterStatus] =
    useState<ReclusterResponse | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<VoiceClustersResponse>(
        `/api/sources/${sourceId}/voice-clusters`,
      );
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

  const handleRecluster = useCallback(async () => {
    setReclustering(true);
    setError(null);
    try {
      const r = await apiPost<ReclusterResponse, {
        min_cluster_size: number;
        min_samples: number;
        noise_threshold: number;
      }>(`/api/sources/${sourceId}/voice-clusters/recluster`, {
        min_cluster_size: minClusterSize,
        min_samples: minSamples,
        noise_threshold: noiseThreshold,
      });
      setReclusterStatus(r);
      await refresh();
    } catch (e) {
      setError(String(e));
    } finally {
      setReclustering(false);
    }
  }, [sourceId, minClusterSize, minSamples, noiseThreshold, refresh]);

  if (loading) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Loading voice clusters…
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
  const reclusterControls = (
    <section
      className="flex flex-col gap-2 rounded border px-3 py-2"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      <div className="flex items-center justify-between gap-2">
        <h3
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--foreground-secondary)" }}
        >
          HDBSCAN re-cluster
        </h3>
        <button
          type="button"
          onClick={handleRecluster}
          disabled={reclustering}
          className="rounded border px-2 py-0.5 text-[11px]"
          style={{
            borderColor: "var(--border)",
            opacity: reclustering ? 0.5 : 1,
            cursor: reclustering ? "wait" : "pointer",
          }}
        >
          {reclustering ? "Re-clustering…" : "Re-cluster"}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-[11px]">
        <label className="flex items-center gap-1">
          <span style={{ color: "var(--foreground-ghost)" }}>min cluster</span>
          <input
            type="number"
            min={2}
            max={50}
            value={minClusterSize}
            onChange={(e) =>
              setMinClusterSize(Math.max(2, Number(e.target.value) || 2))
            }
            disabled={reclustering}
            className="w-12 rounded border px-1 py-0.5 text-right"
            style={{ borderColor: "var(--border)" }}
          />
        </label>
        <label className="flex items-center gap-1">
          <span style={{ color: "var(--foreground-ghost)" }}>min samples</span>
          <input
            type="number"
            min={1}
            max={20}
            value={minSamples}
            onChange={(e) =>
              setMinSamples(Math.max(1, Number(e.target.value) || 1))
            }
            disabled={reclustering}
            className="w-12 rounded border px-1 py-0.5 text-right"
            style={{ borderColor: "var(--border)" }}
          />
        </label>
        <label className="flex items-center gap-1">
          <span style={{ color: "var(--foreground-ghost)" }}>
            noise floor (cos)
          </span>
          <input
            type="number"
            min={0}
            max={1}
            step={0.05}
            value={noiseThreshold}
            onChange={(e) =>
              setNoiseThreshold(
                Math.max(0, Math.min(1, Number(e.target.value) || 0)),
              )
            }
            disabled={reclustering}
            className="w-14 rounded border px-1 py-0.5 text-right"
            style={{ borderColor: "var(--border)" }}
          />
        </label>
        {reclusterStatus && (
          <span style={{ color: "var(--foreground-ghost)" }}>
            Last run: {reclusterStatus.n_clusters} clusters · sizes [
            {reclusterStatus.cluster_sizes.join(", ")}] · {reclusterStatus.n_noise}{" "}
            noise turns (of {reclusterStatus.n_turns_with_embedding} with
            embedding)
          </span>
        )}
      </div>
    </section>
  );

  if (!data || data.speakers.length === 0) {
    return (
      <div className="flex h-full flex-col gap-4 overflow-y-auto custom-scrollbar pr-2">
        {reclusterControls}
        <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
          No voice clusters for this source — pyannote hasn&apos;t run, or all
          turns lack a speaker_label.
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto custom-scrollbar pr-2">
      {reclusterControls}
      {data.speakers.map((sp) => (
        <VoiceClusterSection
          key={sp.speaker_label}
          cluster={sp}
          onSeek={onSeek}
          onAssign={() => setAssigning(sp)}
        />
      ))}

      {assigning && (
        <AssignVoiceModal
          sourceId={sourceId}
          cluster={assigning}
          onClose={() => setAssigning(null)}
          onSaved={() => {
            setAssigning(null);
            refresh();
            onClusterAssigned?.();
          }}
        />
      )}
    </div>
  );
}

interface SectionProps {
  cluster: VoiceCluster;
  onSeek: (seconds: number) => void;
  onAssign: () => void;
}

function VoiceClusterSection({ cluster, onSeek, onAssign }: SectionProps) {
  const [showAll, setShowAll] = useState(false);

  const breakdownEntries = Object.entries(
    cluster.match_method_breakdown ?? {},
  ).sort(
    // Stable display order — known methods first, then null.
    (a, b) => {
      const order = ["voice+face", "voice", "face", "manual", "null"];
      return order.indexOf(a[0]) - order.indexOf(b[0]);
    },
  );

  // Defensive default — a stale API serving the pre-comprehensive
  // payload (sample_turns) won't crash the panel. The cluster just
  // renders with an empty turn list; restart the API to see the data.
  const turns = cluster.turns ?? [];
  const firstTs = cluster.first_ts ?? 0;
  const lastTs = cluster.last_ts ?? 0;
  const visibleTurns = showAll ? turns : turns.slice(0, TURNS_INITIAL_LIMIT);
  const hiddenCount = turns.length - visibleTurns.length;

  return (
    <section
      className="flex flex-col gap-2 rounded border px-3 py-3"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      {/* Header row — label, totals, time range, current dominant person, assign. */}
      <header className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex items-baseline gap-2">
            <h3 className="text-sm font-semibold uppercase tracking-wider">
              {cluster.speaker_label}
            </h3>
            <span
              className="text-[11px]"
              style={{ color: "var(--foreground-ghost)" }}
            >
              {cluster.turn_count} turn{cluster.turn_count === 1 ? "" : "s"} ·{" "}
              {fmtDuration(cluster.total_seconds)} ·{" "}
              {fmtTs(firstTs)}–{fmtTs(lastTs)}
            </span>
          </div>
          <div className="text-[11px]" style={{ color: "var(--foreground-secondary)" }}>
            Currently:{" "}
            {cluster.dominant_person_name ? (
              <>
                <strong>{cluster.dominant_person_name}</strong>
                <span style={{ color: "var(--foreground-ghost)" }}>
                  {" "}
                  ({pct(cluster.dominant_share)} of turns)
                </span>
              </>
            ) : (
              <span style={{ color: "var(--foreground-ghost)" }}>
                Unattributed
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onAssign}
          className="shrink-0 rounded px-3 py-1.5 text-xs font-medium"
          style={{
            backgroundColor: "var(--accent)",
            color: "#000",
            cursor: "pointer",
          }}
        >
          Assign
        </button>
      </header>

      {/* Match-method breakdown — small inline tags. */}
      <div className="flex flex-wrap items-center gap-1.5 text-[10px]">
        {breakdownEntries.map(([method, count]) => (
          <span
            key={method}
            className="rounded px-1.5 py-0.5"
            style={{
              border: `1px solid ${methodColor(method === "null" ? null : method)}`,
              color: methodColor(method === "null" ? null : method),
            }}
          >
            {method}: {count}
          </span>
        ))}
      </div>

      {/* Per-turn list — every turn in chronological order. */}
      {visibleTurns.length > 0 && (
        <ul className="flex flex-col gap-1">
          {visibleTurns.map((t) => (
            <VoiceTurnRow key={t.segment_id} turn={t} onSeek={onSeek} />
          ))}
        </ul>
      )}

      {hiddenCount > 0 && !showAll && (
        <button
          type="button"
          onClick={() => setShowAll(true)}
          className="self-start rounded border px-2 py-1 text-[10px]"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-secondary)",
          }}
        >
          Show all {turns.length} turns ({hiddenCount} hidden)
        </button>
      )}
      {showAll && turns.length > TURNS_INITIAL_LIMIT && (
        <button
          type="button"
          onClick={() => setShowAll(false)}
          className="self-start rounded border px-2 py-1 text-[10px]"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-secondary)",
          }}
        >
          Collapse to first {TURNS_INITIAL_LIMIT}
        </button>
      )}
      {/* Empty-state signal — a stale API or a not-yet-transcribed
          source produces a cluster with zero turns in the payload. */}
      {turns.length === 0 && (
        <div className="text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
          No turns returned for this cluster — either the API is serving an
          older response shape (restart uvicorn to pick up the latest
          voice_clusters.py) or the source isn&apos;t fully transcribed.
        </div>
      )}

      {/* Eligibility footnote — only when the cluster has any non-eligible
          turns to flag. Same surface area as face panel's portrait warnings. */}
      {cluster.embedding_eligible_count < cluster.turn_count && (
        <div className="text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
          {cluster.embedding_eligible_count} of {cluster.turn_count} turns
          eligible for voiceprint enrolment (the rest are sub-300ms with
          NULL embeddings).
        </div>
      )}
    </section>
  );
}

interface TurnRowProps {
  turn: VoiceClusterTurn;
  onSeek: (seconds: number) => void;
}

function VoiceTurnRow({ turn, onSeek }: TurnRowProps) {
  const color = methodColor(turn.match_method);
  return (
    <li className="flex items-baseline gap-2 text-xs">
      <button
        type="button"
        onClick={() => onSeek(turn.start_ts)}
        className="shrink-0 rounded px-1.5 py-0.5 text-[11px] font-mono"
        style={{
          color: "var(--accent)",
          backgroundColor: "var(--surface)",
          cursor: "pointer",
        }}
        title={`Jump to ${fmtTs(turn.start_ts)}`}
      >
        ▸ {fmtTs(turn.start_ts)}–{fmtTs(turn.end_ts)}
      </button>
      <span
        className="shrink-0 text-[10px] font-mono"
        style={{ color: "var(--foreground-ghost)" }}
        title="Turn duration"
      >
        ({fmtTurnDuration(turn.duration)})
      </span>
      {/* Method dot — small coloured marker by attribution method.
          Matches the per-method tags in the cluster header. */}
      <span
        className="shrink-0 inline-block h-1.5 w-1.5 rounded-full"
        style={{ backgroundColor: color }}
        title={`match_method: ${turn.match_method ?? "null"}`}
      />
      <span
        className="min-w-0 flex-1 leading-snug"
        style={{ color: "var(--foreground-secondary)" }}
      >
        {turn.preview_text || (
          <em style={{ color: "var(--foreground-ghost)" }}>
            (no transcript text)
          </em>
        )}
      </span>
    </li>
  );
}
