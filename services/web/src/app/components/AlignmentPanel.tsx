"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/api";
import type {
  AlignmentDisagreement,
  AlignmentDominantPair,
  AlignmentRow,
  IdentityAlignmentResponse,
} from "@/lib/types";

interface Props {
  sourceId: string;
  /** Seek the player when an operator clicks a disagreement row. */
  onSeek: (seconds: number) => void;
}

function fmtTs(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function pct(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${Math.round(n * 100)}%`;
}

// Confidence colour ramp — green for high, amber mid, red low. Used in
// the matrix cells so the operator can scan a clean alignment at a glance.
function confidenceColor(c: number): string {
  if (c >= 0.7) return "#4ade80"; // green
  if (c >= 0.4) return "#fbbf24"; // amber
  if (c >= 0.15) return "#f97316"; // orange
  return "#f87171"; // red — barely-an-alignment
}

function nameOrFallback(
  name: string | null | undefined,
  fallback: string,
): string {
  return name && name.trim() ? name : fallback;
}

export default function AlignmentPanel({ sourceId, onSeek }: Props) {
  const [data, setData] = useState<IdentityAlignmentResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const r = await apiFetch<IdentityAlignmentResponse>(
        `/api/sources/${sourceId}/identity-alignment`,
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

  // O(1) lookup of alignment[face_cluster_id][speaker_label] = row.
  // Stable shape lets the matrix render with a fixed pair of axes.
  const alignmentByPair = useMemo(() => {
    const out = new Map<string, AlignmentRow>();
    if (!data) return out;
    for (const row of data.alignment) {
      out.set(`${row.face_cluster_id}::${row.speaker_label}`, row);
    }
    return out;
  }, [data]);

  if (loading) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Loading alignment…
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
  if (!data) return null;

  const hasFaces = data.face_clusters.length > 0;
  const hasVoices = data.voice_clusters.length > 0;

  if (!hasFaces || !hasVoices) {
    return (
      <div
        className="text-xs leading-relaxed"
        style={{ color: "var(--foreground-ghost)" }}
      >
        Alignment needs both face clusters and voice clusters to be present.
        Currently: {data.face_clusters.length} face cluster
        {data.face_clusters.length === 1 ? "" : "s"} ·{" "}
        {data.voice_clusters.length} voice cluster
        {data.voice_clusters.length === 1 ? "" : "s"}.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto custom-scrollbar pr-2">
      <PairingsList pairings={data.dominant_pairings} alignmentResp={data} />
      <AlignmentMatrix
        alignmentByPair={alignmentByPair}
        alignmentResp={data}
      />
      <DisagreementsList
        disagreements={data.disagreements}
        onSeek={onSeek}
      />
    </div>
  );
}

interface PairingsListProps {
  pairings: AlignmentDominantPair[];
  alignmentResp: IdentityAlignmentResponse;
}

function PairingsList({ pairings, alignmentResp }: PairingsListProps) {
  const faceById = new Map(
    alignmentResp.face_clusters.map((c) => [c.cluster_id, c]),
  );
  const voiceByLabel = new Map(
    alignmentResp.voice_clusters.map((v) => [v.speaker_label, v]),
  );

  return (
    <section className="flex flex-col gap-2">
      <h3
        className="text-[11px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--foreground-ghost)" }}
      >
        Dominant pairings ({pairings.length})
      </h3>
      <p className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
        Greedy 1:1 best mapping over the alignment matrix below. Each face
        cluster and each voice cluster is claimed at most once, by confidence
        descending.
      </p>
      {pairings.length === 0 ? (
        <div
          className="rounded border px-3 py-2 text-xs"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-ghost)",
          }}
        >
          No pairings — the matrix is empty or every overlap is below
          threshold.
        </div>
      ) : (
        <ul className="flex flex-col gap-1.5">
          {pairings.map((p) => {
            const face = faceById.get(p.face_cluster_id);
            const voice = voiceByLabel.get(p.speaker_label);
            const faceName = nameOrFallback(
              face?.dominant_person_name,
              `Cluster ${p.face_cluster_id}`,
            );
            const voiceName = nameOrFallback(
              voice?.dominant_person_name,
              p.speaker_label,
            );
            const consistent =
              face?.dominant_person_id &&
              voice?.dominant_person_id &&
              face.dominant_person_id === voice.dominant_person_id;
            return (
              <li
                key={`${p.face_cluster_id}-${p.speaker_label}`}
                className="flex items-center justify-between rounded border px-3 py-2 text-xs"
                style={{
                  borderColor: consistent
                    ? "var(--accent)"
                    : "var(--border)",
                  backgroundColor: "var(--background-deep)",
                }}
              >
                <div className="flex flex-col gap-0.5">
                  <div>
                    <strong>Cluster {p.face_cluster_id}</strong>
                    <span style={{ color: "var(--foreground-ghost)" }}>
                      {" → "}
                    </span>
                    <strong>{p.speaker_label}</strong>
                  </div>
                  <div
                    className="text-[10px]"
                    style={{ color: "var(--foreground-ghost)" }}
                  >
                    Face: {faceName} · Voice: {voiceName}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-0.5">
                  <span
                    className="text-xs font-mono"
                    style={{ color: confidenceColor(p.confidence) }}
                  >
                    {pct(p.confidence)}
                  </span>
                  <span
                    className="text-[10px]"
                    style={{ color: "var(--foreground-ghost)" }}
                  >
                    {p.overlap_count} overlap frames
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}

interface MatrixProps {
  alignmentByPair: Map<string, AlignmentRow>;
  alignmentResp: IdentityAlignmentResponse;
}

function AlignmentMatrix({ alignmentByPair, alignmentResp }: MatrixProps) {
  // Top-N axes so the matrix doesn't explode visually. Most podcasts
  // have <6 clusters each side; multi-cam sports could blow up.
  const FACE_AXIS_LIMIT = 8;
  const VOICE_AXIS_LIMIT = 8;
  const faceAxis = alignmentResp.face_clusters.slice(0, FACE_AXIS_LIMIT);
  const voiceAxis = alignmentResp.voice_clusters.slice(0, VOICE_AXIS_LIMIT);

  return (
    <section className="flex flex-col gap-2">
      <h3
        className="text-[11px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--foreground-ghost)" }}
      >
        Overlap matrix
      </h3>
      <p className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
        Cell value = confidence (min of face share and voice share). Rows
        sorted by face-cluster size, columns by voice-cluster airtime.
      </p>
      <div className="overflow-x-auto">
        <table
          className="border-collapse text-[11px]"
          style={{ minWidth: "100%" }}
        >
          <thead>
            <tr>
              <th
                className="px-2 py-1 text-left"
                style={{ color: "var(--foreground-ghost)" }}
              >
                Face → Voice
              </th>
              {voiceAxis.map((v) => (
                <th
                  key={v.speaker_label}
                  className="px-2 py-1 text-left"
                  style={{ color: "var(--foreground-secondary)" }}
                >
                  <div>{v.speaker_label}</div>
                  <div
                    className="text-[9px] font-normal"
                    style={{ color: "var(--foreground-ghost)" }}
                  >
                    {nameOrFallback(v.dominant_person_name, "—")}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {faceAxis.map((c) => (
              <tr key={c.cluster_id}>
                <td
                  className="px-2 py-1"
                  style={{ color: "var(--foreground-secondary)" }}
                >
                  <div>Cluster {c.cluster_id}</div>
                  <div
                    className="text-[9px]"
                    style={{ color: "var(--foreground-ghost)" }}
                  >
                    {nameOrFallback(c.dominant_person_name, "—")}
                  </div>
                </td>
                {voiceAxis.map((v) => {
                  const row = alignmentByPair.get(
                    `${c.cluster_id}::${v.speaker_label}`,
                  );
                  if (!row) {
                    return (
                      <td
                        key={v.speaker_label}
                        className="px-2 py-1 text-center"
                        style={{ color: "var(--foreground-ghost)" }}
                      >
                        —
                      </td>
                    );
                  }
                  return (
                    <td
                      key={v.speaker_label}
                      className="px-2 py-1 text-center"
                      title={
                        `face_share ${pct(row.face_cluster_share)} · ` +
                        `voice_share ${pct(row.voice_cluster_share)} · ` +
                        `overlap ${row.overlap_count} (active ${row.active_overlap_count})`
                      }
                    >
                      <div
                        className="font-mono"
                        style={{ color: confidenceColor(row.confidence) }}
                      >
                        {pct(row.confidence)}
                      </div>
                      <div
                        className="text-[9px]"
                        style={{ color: "var(--foreground-ghost)" }}
                      >
                        {row.overlap_count}
                      </div>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {(alignmentResp.face_clusters.length > FACE_AXIS_LIMIT
        || alignmentResp.voice_clusters.length > VOICE_AXIS_LIMIT) && (
        <div className="text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
          Matrix capped at {FACE_AXIS_LIMIT} × {VOICE_AXIS_LIMIT}; trailing
          clusters omitted.
        </div>
      )}
    </section>
  );
}

interface DisagreementsProps {
  disagreements: AlignmentDisagreement[];
  onSeek: (seconds: number) => void;
}

function DisagreementsList({ disagreements, onSeek }: DisagreementsProps) {
  return (
    <section className="flex flex-col gap-2">
      <h3
        className="text-[11px] font-semibold uppercase tracking-wider"
        style={{ color: "var(--foreground-ghost)" }}
      >
        Disagreements ({disagreements.length})
      </h3>
      <p className="text-[11px]" style={{ color: "var(--foreground-ghost)" }}>
        Turns where the dominant on-screen face cluster's identity differs from
        the turn's voice attribution. Operator worklist — either the face was
        a reaction shot the ASD let through, or the voice attribution is
        wrong. Sorted by turn duration descending.
      </p>
      {disagreements.length === 0 ? (
        <div
          className="rounded border px-3 py-2 text-xs"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-ghost)",
          }}
        >
          No disagreements detected — every attributed turn matches the
          dominant on-screen cluster.
        </div>
      ) : (
        <ul className="flex flex-col gap-1">
          {disagreements.map((d) => (
            <li
              key={d.segment_id}
              className="flex items-start gap-2 rounded border px-3 py-2 text-xs"
              style={{
                borderColor: "var(--border)",
                backgroundColor: "var(--background-deep)",
              }}
            >
              <button
                type="button"
                onClick={() => onSeek(d.start_ts)}
                className="shrink-0 rounded px-1 py-0.5 text-[11px] font-mono"
                style={{
                  color: "var(--accent)",
                  backgroundColor: "var(--surface)",
                  cursor: "pointer",
                }}
                title={`Jump to ${fmtTs(d.start_ts)}`}
              >
                ▸ {fmtTs(d.start_ts)}
              </button>
              <div className="flex min-w-0 flex-col gap-0.5">
                <div>
                  <strong>{d.speaker_label}</strong>
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    {" "}
                    →{" "}
                  </span>
                  Voice attributed to{" "}
                  <strong>
                    {nameOrFallback(d.speaker_person_name, "(unknown)")}
                  </strong>
                </div>
                <div>
                  <strong>Cluster {d.face_cluster_id}</strong>
                  <span style={{ color: "var(--foreground-ghost)" }}>
                    {" "}
                    →{" "}
                  </span>
                  On-screen face dominantly{" "}
                  <strong>
                    {nameOrFallback(d.face_person_name, "(unknown)")}
                  </strong>
                </div>
                <div
                  className="text-[10px]"
                  style={{ color: "var(--foreground-ghost)" }}
                >
                  {fmtTs(d.start_ts)}–{fmtTs(d.end_ts)} ·{" "}
                  {d.active_overlap_count} active overlap frame
                  {d.active_overlap_count === 1 ? "" : "s"}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
