"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { apiFetch } from "@/lib/api";
import type {
  FaceTranscriptResponse,
  FaceTranscriptSegment,
} from "@/lib/types";

interface Props {
  sourceId: string;
  /** Seek the YouTube/video preview when the operator clicks a segment. */
  onSeek: (seconds: number) => void;
}

function fmtTs(s: number): string {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = Math.floor(s % 60);
  if (h > 0) {
    return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  }
  return `${m}:${String(sec).padStart(2, "0")}`;
}

function fmtDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m === 0) return `${s}s`;
  return `${m}m ${String(s).padStart(2, "0")}s`;
}

// Stable per-cluster colour, so the same face shows the same hue across
// segments (helps the eye track who's speaking on a scroll). Pulled
// from the same palette family the face overlay uses.
const CLUSTER_PALETTE = [
  "#60a5fa", "#fbbf24", "#4ade80", "#c084fc",
  "#f87171", "#22d3ee", "#fb923c", "#a3e635",
  "#f472b6", "#94a3b8", "#facc15", "#34d399",
];
function colorForCluster(cid: number | null): string {
  if (cid === null) return "var(--foreground-ghost)";
  return CLUSTER_PALETTE[cid % CLUSTER_PALETTE.length];
}

export default function FaceTranscriptPanel({ sourceId, onSeek }: Props) {
  const [mouthThreshold, setMouthThreshold] = useState(0.045);
  const [smoothGap, setSmoothGap] = useState(3.0);
  const [minSegment, setMinSegment] = useState(1.0);

  const [data, setData] = useState<FaceTranscriptResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTranscript = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const qs = new URLSearchParams({
        mouth_threshold: String(mouthThreshold),
        smooth_gap: String(smoothGap),
        min_segment: String(minSegment),
      });
      const r = await apiFetch<FaceTranscriptResponse>(
        `/api/sources/${sourceId}/face-transcript?${qs.toString()}`,
      );
      setData(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [sourceId, mouthThreshold, smoothGap, minSegment]);

  useEffect(() => {
    void fetchTranscript();
    // Only fetch on first load; subsequent fetches happen via the
    // Apply button so the operator doesn't trigger a heavy query on
    // every slider keystroke.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceId]);

  // Speaker-share summary from the current segments.
  const summary = useMemo(() => {
    if (!data) return [];
    const by: Record<string, {
      speaker_label: string;
      cid: number | null;
      person_name: string | null;
      segments: number;
      seconds: number;
      words: number;
    }> = {};
    for (const seg of data.segments) {
      const key = seg.speaker_label;
      if (!by[key]) {
        by[key] = {
          speaker_label: seg.speaker_label,
          cid: seg.face_cluster_id,
          person_name: seg.person_name,
          segments: 0,
          seconds: 0,
          words: 0,
        };
      }
      by[key].segments += 1;
      by[key].seconds += seg.duration;
      by[key].words += seg.text ? seg.text.split(/\s+/).filter(Boolean).length : 0;
    }
    return Object.values(by).sort((a, b) => b.seconds - a.seconds);
  }, [data]);

  if (loading && !data) {
    return (
      <div className="text-xs" style={{ color: "var(--foreground-ghost)" }}>
        Loading face-driven transcript…
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
  if (!data) {
    return null;
  }

  return (
    <div className="flex h-full flex-col gap-3 overflow-y-auto custom-scrollbar pr-2">
      {/* Controls + summary row */}
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
            Face-driven segmentation
          </h3>
          <button
            type="button"
            onClick={() => void fetchTranscript()}
            disabled={loading}
            className="rounded border px-2 py-0.5 text-[11px]"
            style={{
              borderColor: "var(--border)",
              opacity: loading ? 0.5 : 1,
              cursor: loading ? "wait" : "pointer",
            }}
          >
            {loading ? "Loading…" : "Apply"}
          </button>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-[11px]">
          <label className="flex items-center gap-1">
            <span style={{ color: "var(--foreground-ghost)" }}>mouth thresh</span>
            <input
              type="number"
              min={0}
              max={1}
              step={0.005}
              value={mouthThreshold}
              onChange={(e) => setMouthThreshold(Number(e.target.value) || 0)}
              disabled={loading}
              className="w-16 rounded border px-1 py-0.5 text-right"
              style={{ borderColor: "var(--border)" }}
            />
          </label>
          <label className="flex items-center gap-1">
            <span style={{ color: "var(--foreground-ghost)" }}>smooth gap (s)</span>
            <input
              type="number"
              min={0}
              max={30}
              step={0.5}
              value={smoothGap}
              onChange={(e) => setSmoothGap(Number(e.target.value) || 0)}
              disabled={loading}
              className="w-14 rounded border px-1 py-0.5 text-right"
              style={{ borderColor: "var(--border)" }}
            />
          </label>
          <label className="flex items-center gap-1">
            <span style={{ color: "var(--foreground-ghost)" }}>min seg (s)</span>
            <input
              type="number"
              min={0}
              max={30}
              step={0.5}
              value={minSegment}
              onChange={(e) => setMinSegment(Number(e.target.value) || 0)}
              disabled={loading}
              className="w-14 rounded border px-1 py-0.5 text-right"
              style={{ borderColor: "var(--border)" }}
            />
          </label>
        </div>
      </section>

      {/* Speaker share summary */}
      {summary.length > 0 && (
        <section
          className="flex flex-col gap-1 rounded border px-3 py-2"
          style={{
            borderColor: "var(--border)",
            backgroundColor: "var(--background-deep)",
          }}
        >
          <h3
            className="text-[11px] font-semibold uppercase tracking-wider"
            style={{ color: "var(--foreground-secondary)" }}
          >
            Speaker share ({data.segments.length} segments)
          </h3>
          <div className="flex flex-wrap gap-2 text-[11px]">
            {summary.map((s) => (
              <span
                key={s.speaker_label}
                className="inline-flex items-center gap-1 rounded px-2 py-0.5"
                style={{ backgroundColor: "var(--background)" }}
              >
                <span
                  className="inline-block h-2 w-2 rounded-full"
                  style={{ backgroundColor: colorForCluster(s.cid) }}
                />
                <strong>{s.speaker_label}</strong>
                {s.person_name && (
                  <span style={{ color: "var(--foreground-secondary)" }}>
                    {" "}→ {s.person_name}
                  </span>
                )}
                <span style={{ color: "var(--foreground-ghost)" }}>
                  {" "}· {fmtDuration(s.seconds)} · {s.words} words · {s.segments} segs
                </span>
              </span>
            ))}
          </div>
        </section>
      )}

      {/* Chronological segments */}
      <section className="flex flex-col gap-2">
        {data.segments.map((seg, idx) => (
          <SegmentRow
            key={`${seg.start}-${idx}`}
            segment={seg}
            onSeek={onSeek}
          />
        ))}
      </section>
    </div>
  );
}

interface SegmentRowProps {
  segment: FaceTranscriptSegment;
  onSeek: (seconds: number) => void;
}

function SegmentRow({ segment, onSeek }: SegmentRowProps) {
  const color = colorForCluster(segment.face_cluster_id);
  return (
    <button
      type="button"
      onClick={() => onSeek(segment.start)}
      className="flex flex-col items-start gap-1 rounded border px-3 py-2 text-left transition-colors hover:bg-[var(--background-deep)]"
      style={{
        borderColor: "var(--border)",
        backgroundColor: "var(--background-deep)",
      }}
    >
      <div className="flex items-center gap-2 text-[11px]">
        <span
          className="inline-block h-2 w-2 rounded-full"
          style={{ backgroundColor: color }}
        />
        <span style={{ color: "var(--foreground-ghost)" }}>
          {fmtTs(segment.start)} – {fmtTs(segment.end)}
        </span>
        <span className="font-semibold uppercase tracking-wider">
          {segment.speaker_label}
        </span>
        {segment.person_name && (
          <span style={{ color: "var(--foreground-secondary)" }}>
            → <strong>{segment.person_name}</strong>
          </span>
        )}
        <span style={{ color: "var(--foreground-ghost)" }}>
          · {fmtDuration(segment.duration)}
        </span>
      </div>
      {segment.text ? (
        <p className="text-xs leading-snug">{segment.text}</p>
      ) : (
        <p
          className="text-[11px] italic"
          style={{ color: "var(--foreground-ghost)" }}
        >
          (no transcript text in this window)
        </p>
      )}
    </button>
  );
}
