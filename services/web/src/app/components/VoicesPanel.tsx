"use client";

import { useCallback, useEffect, useState } from "react";

import { apiFetch } from "@/lib/api";
import type {
  VoiceCluster,
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

function pct(n: number | null): string {
  if (n === null) return "—";
  return `${Math.round(n * 100)}%`;
}

// Match-method colours — same mapping as the YouTube overlay so the
// Voices tab reads consistently with the face boxes drawn over the
// player. See speaker-identification.md § Concepts → Match method.
function methodColor(method: string): string {
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

export default function VoicesPanel({
  sourceId,
  onSeek,
  onClusterAssigned,
}: Props) {
  const [data, setData] = useState<VoiceClustersResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState<VoiceCluster | null>(null);

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
  if (!data || data.speakers.length === 0) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        No voice clusters for this source — pyannote hasn't run, or all turns
        lack a speaker_label.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto custom-scrollbar pr-2">
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
  const breakdownEntries = Object.entries(cluster.match_method_breakdown).sort(
    // Stable display order — known methods first, then null.
    (a, b) => {
      const order = ["voice+face", "voice", "face", "manual", "null"];
      return order.indexOf(a[0]) - order.indexOf(b[0]);
    },
  );

  return (
    <section
      className="flex flex-col gap-2 rounded border px-3 py-3"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      {/* Header row — label, totals, current dominant person, assign button. */}
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
              {fmtDuration(cluster.total_seconds)}
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
              border: `1px solid ${methodColor(method)}`,
              color: methodColor(method),
            }}
          >
            {method}: {count}
          </span>
        ))}
      </div>

      {/* Sample turns — click to seek the player. */}
      {cluster.sample_turns.length > 0 && (
        <ul className="flex flex-col gap-1">
          {cluster.sample_turns.map((t) => (
            <li
              key={t.segment_id}
              className="flex items-baseline gap-2 text-xs"
            >
              <button
                type="button"
                onClick={() => onSeek(t.start_ts)}
                className="shrink-0 rounded px-1 py-0.5 text-[11px] font-mono"
                style={{
                  color: "var(--accent)",
                  backgroundColor: "var(--surface)",
                  cursor: "pointer",
                }}
                title={`Jump to ${fmtTs(t.start_ts)}`}
              >
                ▸ {fmtTs(t.start_ts)}
              </button>
              <span
                className="min-w-0 truncate"
                style={{ color: "var(--foreground-secondary)" }}
              >
                {t.preview_text || (
                  <em style={{ color: "var(--foreground-ghost)" }}>
                    (no transcript text)
                  </em>
                )}
              </span>
            </li>
          ))}
        </ul>
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
