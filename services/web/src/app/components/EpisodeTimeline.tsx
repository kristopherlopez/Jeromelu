"use client";

import { useMemo, useState } from "react";
import type { ClaimDetail, TranscriptChunk } from "@/lib/types";
import { CLAIM_TYPE_COLORS } from "@/lib/constants";

interface Props {
  claims: ClaimDetail[];
  chunks: TranscriptChunk[];
  currentTime: number;
  onSeek: (seconds: number) => void;
}

export default function EpisodeTimeline({ claims, chunks, currentTime, onSeek }: Props) {
  const [excluded, setExcluded] = useState<Set<string>>(new Set());

  // Source.duration_seconds isn't on the API yet, so derive duration from the
  // furthest chunk/claim end-timestamp.
  const duration = useMemo(() => {
    let max = 0;
    for (const c of chunks) {
      if (c.end_ts !== null && c.end_ts > max) max = c.end_ts;
    }
    for (const c of claims) {
      if (c.end_ts !== null && c.end_ts > max) max = c.end_ts;
      if (c.start_ts !== null && c.start_ts > max) max = c.start_ts;
    }
    return max;
  }, [claims, chunks]);

  const types = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of claims) {
      if (c.start_ts === null) continue;
      counts.set(c.claim_type, (counts.get(c.claim_type) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([type, count]) => ({ type, count }))
      .sort((a, b) => b.count - a.count);
  }, [claims]);

  const visibleClaims = useMemo(
    () =>
      claims.filter(
        (c) => c.start_ts !== null && !excluded.has(c.claim_type),
      ),
    [claims, excluded],
  );

  const toggle = (type: string) => {
    setExcluded((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const hasData = duration > 0 && claims.length > 0;
  const playheadPct = hasData
    ? Math.min(100, Math.max(0, (currentTime / duration) * 100))
    : 0;

  return (
    <section
      className="rounded-lg border p-4"
      style={{ borderColor: "var(--border)", backgroundColor: "var(--background-deep)" }}
    >
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--foreground-ghost)" }}>
          Episode timeline
        </h2>
        {excluded.size > 0 && (
          <button
            onClick={() => setExcluded(new Set())}
            className="text-[10px] uppercase tracking-wider hover:underline cursor-pointer"
            style={{ color: "var(--foreground-ghost)" }}
          >
            Clear all
          </button>
        )}
      </div>

      {!hasData && (
        <p className="mb-3 text-xs" style={{ color: "var(--foreground-ghost)" }}>
          No timestamped claims on this source yet.
        </p>
      )}

      <div className="flex flex-wrap gap-1.5 mb-4">
        {types.map(({ type, count }) => {
          const color = CLAIM_TYPE_COLORS[type] || "var(--foreground-muted)";
          const active = !excluded.has(type);
          return (
            <button
              key={type}
              onClick={() => toggle(type)}
              className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium uppercase cursor-pointer transition-colors"
              style={{
                backgroundColor: active ? `${color}22` : "rgba(255,255,255,0.04)",
                color: active ? color : "var(--foreground-muted)",
                border: `1px solid ${active ? `${color}55` : "transparent"}`,
                opacity: active ? 1 : 0.55,
              }}
            >
              <span
                className="inline-block w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: color }}
              />
              {type.replace("_", " ")} ({count})
            </button>
          );
        })}
        <span
          title="Speaker diarisation lands with Deepgram — not wired up yet"
          aria-disabled="true"
          className="flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium uppercase"
          style={{
            color: "var(--foreground-ghost)",
            border: "1px dashed var(--border)",
            cursor: "not-allowed",
            opacity: 0.5,
          }}
        >
          <span
            className="inline-block w-1.5 h-1.5 rounded-full"
            style={{ backgroundColor: "var(--foreground-ghost)" }}
          />
          Speaker changes (soon)
        </span>
      </div>

      <div
        className="relative w-full rounded"
        style={{
          height: 56,
          backgroundColor: "rgba(255,255,255,0.03)",
          border: "1px solid var(--border)",
        }}
      >
        <div
          className="absolute top-0 bottom-0"
          style={{
            left: `${playheadPct}%`,
            width: 1,
            backgroundColor: "var(--accent)",
            boxShadow: "0 0 6px var(--accent)",
            pointerEvents: "none",
          }}
        />
        {visibleClaims.map((c) => {
          const left = ((c.start_ts ?? 0) / duration) * 100;
          const color = CLAIM_TYPE_COLORS[c.claim_type] || "var(--foreground-muted)";
          const tip = [
            c.claim_type.replace("_", " ").toUpperCase(),
            c.player_name,
            c.claim_text,
          ]
            .filter(Boolean)
            .join(" · ");
          return (
            <button
              key={c.claim_id}
              onClick={() => onSeek(c.start_ts ?? 0)}
              title={tip}
              aria-label={tip}
              className="absolute top-1 bottom-1 cursor-pointer hover:opacity-100"
              style={{
                left: `calc(${left}% - 1px)`,
                width: 2,
                backgroundColor: color,
                opacity: 0.85,
                border: "none",
                padding: 0,
              }}
            />
          );
        })}
        <div
          className="absolute -bottom-5 left-0 right-0 flex justify-between text-[10px]"
          style={{ color: "var(--foreground-ghost)" }}
        >
          <span>0:00</span>
          <span>{formatTimecode(duration)}</span>
        </div>
      </div>

      <p className="mt-7 text-[10px]" style={{ color: "var(--foreground-ghost)" }}>
        Click a marker to jump to that moment.
      </p>
    </section>
  );
}

function formatTimecode(seconds: number): string {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const r = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(r).padStart(2, "0")}`;
  return `${m}:${String(r).padStart(2, "0")}`;
}
