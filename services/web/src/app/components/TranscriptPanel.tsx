"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Pencil } from "lucide-react";
import { useVirtualizer } from "@tanstack/react-virtual";
import type { TranscriptChunk, ClaimDetail, Speaker } from "@/lib/types";
import { apiPatch } from "@/lib/api";
import { CLAIM_TYPE_COLORS } from "@/lib/constants";

// ---------------------------------------------------------------------------
// Speaker palette — stable per speaker_label so a renamed speaker keeps colour
// ---------------------------------------------------------------------------

const SPEAKER_PALETTE = [
  "#60a5fa", // blue
  "#34d399", // green
  "#fbbf24", // amber
  "#f472b6", // pink
  "#a78bfa", // violet
  "#22d3ee", // cyan
  "#fb7185", // rose
];

function speakerColor(label: string | null | undefined): string {
  if (!label) return "var(--foreground-muted)";
  let hash = 0;
  for (let i = 0; i < label.length; i++) {
    hash = (hash * 31 + label.charCodeAt(i)) >>> 0;
  }
  return SPEAKER_PALETTE[hash % SPEAKER_PALETTE.length];
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function chunkText(chunk: TranscriptChunk): string {
  return chunk.clean_text ?? chunk.raw_text;
}

function findCoveringClaim(
  ts: number,
  claims: ClaimDetail[]
): ClaimDetail | null {
  for (const c of claims) {
    if (
      c.start_ts != null &&
      c.end_ts != null &&
      ts >= c.start_ts &&
      ts < c.end_ts
    ) {
      return c;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Group consecutive chunks by speaker_segment_id into turns
// ---------------------------------------------------------------------------

interface Turn {
  segmentId: string | null;
  speakerLabel: string | null;
  startTs: number;
  chunks: TranscriptChunk[];
}

function groupTurns(
  chunks: TranscriptChunk[],
  speakers: Speaker[]
): Turn[] {
  const speakerById = new Map(speakers.map((s) => [s.segment_id, s]));
  const turns: Turn[] = [];

  for (const ch of chunks) {
    const last = turns[turns.length - 1];
    const segId = ch.speaker_segment_id ?? null;
    if (last && last.segmentId === segId) {
      last.chunks.push(ch);
      continue;
    }
    const speaker = segId ? speakerById.get(segId) : undefined;
    turns.push({
      segmentId: segId,
      speakerLabel: speaker?.speaker_label ?? null,
      startTs: ch.start_ts ?? 0,
      chunks: [ch],
    });
  }

  return turns;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  chunks: TranscriptChunk[];
  claims: ClaimDetail[];
  speakers: Speaker[];
  currentTime: number;
  onSeek: (seconds: number) => void;
  onSpeakerRenamed?: (segmentId: string, newLabel: string) => void;
}

export default function TranscriptPanel({
  chunks,
  claims,
  speakers,
  currentTime,
  onSeek,
  onSpeakerRenamed,
}: Props) {
  const turns = useMemo(() => groupTurns(chunks, speakers), [chunks, speakers]);
  const sortedClaims = useMemo(
    () => claims.filter((c) => c.start_ts != null && c.end_ts != null),
    [claims]
  );

  // Map original speaker_label → effective label (for inline rename without
  // a round-trip refresh). Keyed by label rather than segment_id so a rename
  // applies to every turn from the same speaker.
  const [labelOverrides, setLabelOverrides] = useState<Record<string, string>>(
    {}
  );
  const effectiveLabel = (label: string | null) =>
    label && labelOverrides[label] ? labelOverrides[label] : label;

  const [editingSegmentId, setEditingSegmentId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");

  const scrollRef = useRef<HTMLDivElement>(null);

  // Virtualize turns. 3h podcasts produce 1000+ turns — mounting them
  // all freezes the page on initial render. We virtualize at the turn
  // level (not chunk level) so the within-turn structure stays simple
  // and the speaker-rename / claim-overlay logic doesn't need to know
  // anything about windowing.
  const virtualizer = useVirtualizer({
    count: turns.length,
    getScrollElement: () => scrollRef.current,
    // Conservative starting estimate. measureElement (below) replaces
    // this with the real height on first mount of each row.
    estimateSize: () => 110,
    overscan: 8,
  });

  // Index of the turn containing the active timestamp. Recomputed only
  // when currentTime crosses a turn boundary so the auto-scroll effect
  // doesn't fire every video-frame tick.
  const activeTurnIndex = useMemo(() => {
    if (turns.length === 0) return -1;
    // Turns are in chronological order — find the last one whose
    // startTs <= currentTime. Binary search keeps this cheap on very
    // long sources.
    let lo = 0;
    let hi = turns.length - 1;
    let found = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >>> 1;
      if (turns[mid].startTs <= currentTime) {
        found = mid;
        lo = mid + 1;
      } else {
        hi = mid - 1;
      }
    }
    return found;
  }, [turns, currentTime]);

  const lastScrolledIndex = useRef(-1);
  const lastScrollTime = useRef(0);

  useEffect(() => {
    if (activeTurnIndex < 0) return;
    if (activeTurnIndex === lastScrolledIndex.current) return;
    const now = Date.now();
    if (now - lastScrollTime.current < 800) return;
    lastScrolledIndex.current = activeTurnIndex;
    lastScrollTime.current = now;
    virtualizer.scrollToIndex(activeTurnIndex, {
      align: "center",
      behavior: "smooth",
    });
  }, [activeTurnIndex, virtualizer]);

  async function commitRename(segmentId: string, originalLabel: string | null) {
    const next = editValue.trim();
    setEditingSegmentId(null);
    if (!next || !originalLabel || next === effectiveLabel(originalLabel))
      return;
    try {
      await apiPatch(`/api/sources/speakers/${segmentId}`, {
        speaker_label: next,
      });
      setLabelOverrides((prev) => ({ ...prev, [originalLabel]: next }));
      onSpeakerRenamed?.(segmentId, next);
    } catch (err) {
      console.error("Speaker rename failed:", err);
    }
  }

  return (
    <div
      className="rounded-lg border relative flex flex-col h-full min-h-0"
      style={{ borderColor: "var(--border)" }}
    >
      <div
        className="flex items-center justify-between px-4 py-2.5 border-b shrink-0"
        style={{ borderColor: "var(--border)" }}
      >
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--foreground-ghost)" }}
        >
          Transcript &middot; {turns.length} turns &middot; {claims.length}{" "}
          claims
        </span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 min-h-0 custom-scrollbar"
      >
        <div
          className="text-[0.8125rem] leading-[1.8] relative"
          style={{
            // The virtualizer needs a known total height for its absolute-
            // positioned rows. Without this the scroll container would
            // collapse and the virtualization would see height=0.
            height: virtualizer.getTotalSize(),
            width: "100%",
          }}
        >
          {virtualizer.getVirtualItems().map((virtualRow) => {
            const turn = turns[virtualRow.index];
            const turnIdx = virtualRow.index;
            const color = speakerColor(turn.speakerLabel);
            const displayLabel =
              effectiveLabel(turn.speakerLabel) ?? "Unknown";
            const isEditing =
              turn.segmentId !== null && editingSegmentId === turn.segmentId;

            return (
              <div
                key={`turn-${turnIdx}`}
                ref={virtualizer.measureElement}
                data-index={virtualRow.index}
                className="flex flex-col"
                style={{
                  position: "absolute",
                  top: 0,
                  left: 0,
                  right: 0,
                  transform: `translateY(${virtualRow.start}px)`,
                  borderLeft: `2px solid ${color}`,
                  paddingLeft: "10px",
                  // Match the previous flex-gap-3 vertical rhythm.
                  paddingBottom: "12px",
                }}
              >
                {/* Turn header */}
                <div className="flex items-center gap-2 mb-1">
                  {isEditing ? (
                    <input
                      autoFocus
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onBlur={() =>
                        commitRename(turn.segmentId!, turn.speakerLabel)
                      }
                      onKeyDown={(e) => {
                        if (e.key === "Enter") {
                          commitRename(turn.segmentId!, turn.speakerLabel);
                        } else if (e.key === "Escape") {
                          setEditingSegmentId(null);
                        }
                      }}
                      className="text-[11px] font-semibold uppercase tracking-wider border rounded px-1.5 py-0.5"
                      style={{
                        borderColor: color,
                        color,
                        backgroundColor: "var(--background-deep)",
                        outline: "none",
                      }}
                    />
                  ) : (
                    <button
                      onClick={() => {
                        if (!turn.segmentId) return;
                        setEditValue(displayLabel);
                        setEditingSegmentId(turn.segmentId);
                      }}
                      disabled={!turn.segmentId}
                      className="group inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-wider"
                      style={{ color }}
                      title={
                        turn.segmentId ? "Click to rename" : undefined
                      }
                    >
                      {displayLabel}
                      {turn.segmentId && (
                        <Pencil
                          size={10}
                          className="opacity-0 group-hover:opacity-100 transition-opacity"
                        />
                      )}
                    </button>
                  )}
                  <button
                    onClick={() => onSeek(turn.startTs)}
                    className="text-[10px] tabular-nums"
                    style={{ color: "var(--foreground-ghost)" }}
                  >
                    [{formatTimestamp(turn.startTs)}]
                  </button>
                </div>

                {/* Turn body — chunks rendered inline; paragraph_break inserts visual break */}
                <div>
                  {turn.chunks.map((chunk, chunkIdx) => {
                    const ts = chunk.start_ts ?? 0;
                    const endTs = chunk.end_ts ?? ts;
                    const isActive = currentTime >= ts && currentTime < endTs;
                    const coveringClaim = findCoveringClaim(ts, sortedClaims);
                    const claimColor = coveringClaim
                      ? CLAIM_TYPE_COLORS[coveringClaim.claim_type] ||
                        "#71717a"
                      : null;

                    let textColor: string;
                    let bgColor: string;
                    if (isActive) {
                      textColor = "var(--foreground)";
                      bgColor = "var(--accent-border)";
                    } else if (coveringClaim) {
                      textColor = "var(--foreground)";
                      bgColor = claimColor + "12";
                    } else {
                      textColor = "var(--foreground-muted)";
                      bgColor = "transparent";
                    }

                    const text = chunkText(chunk).trim();
                    if (!text) return null;

                    // Insert a paragraph break before chunks marked as such
                    // (skip the first chunk of the turn — turn header is the break).
                    const showBreak =
                      chunk.paragraph_break && chunkIdx > 0;

                    return (
                      <span key={chunk.chunk_id}>
                        {showBreak && (
                          <span style={{ display: "block", height: "0.5em" }} />
                        )}
                        <span
                          className="cursor-pointer transition-colors duration-300"
                          onClick={() => onSeek(ts)}
                          style={{
                            color: textColor,
                            backgroundColor: bgColor,
                            borderRadius:
                              isActive || coveringClaim ? "2px" : undefined,
                            padding:
                              isActive || coveringClaim ? "1px 3px" : undefined,
                          }}
                        >
                          {text}
                          {coveringClaim && chunkIdx === turn.chunks.length - 1
                            ? ""
                            : " "}
                        </span>
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-8 rounded-b-lg pointer-events-none"
        style={{
          background:
            "linear-gradient(to top, var(--background), transparent)",
        }}
      />
    </div>
  );
}
