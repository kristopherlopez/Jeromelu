"use client";

import { useEffect, useMemo, useRef } from "react";
import type { TranscriptChunk, ClaimDetail } from "@/lib/types";
import { CLAIM_TYPE_COLORS } from "@/lib/constants";

function chunkText(chunk: TranscriptChunk): string {
  return chunk.clean_text ?? chunk.raw_text;
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

// ---------------------------------------------------------------------------
// Build a flat list of inline tokens: words and claim markers interleaved
// ---------------------------------------------------------------------------

interface WordToken {
  kind: "word";
  text: string;
  ts: number;
}

interface ClaimMarker {
  kind: "claim";
  claim: ClaimDetail;
}

type Token = WordToken | ClaimMarker;

function buildTokens(
  chunks: TranscriptChunk[],
  claims: ClaimDetail[]
): Token[] {
  // Sort claims by start_ts
  const sorted = claims
    .filter((c) => c.start_ts != null)
    .sort((a, b) => a.start_ts! - b.start_ts!);

  const tokens: Token[] = [];
  let claimIdx = 0;

  for (const chunk of chunks) {
    const ts = chunk.start_ts ?? 0;

    // Insert any claim markers that start before/at this chunk
    while (claimIdx < sorted.length && sorted[claimIdx].start_ts! <= ts) {
      tokens.push({ kind: "claim", claim: sorted[claimIdx] });
      claimIdx++;
    }

    // Add the chunk's words as a single word token
    const text = chunkText(chunk).trim();
    if (text) {
      tokens.push({ kind: "word", text, ts });
    }
  }

  // Any remaining claims after the last chunk
  while (claimIdx < sorted.length) {
    tokens.push({ kind: "claim", claim: sorted[claimIdx] });
    claimIdx++;
  }

  return tokens;
}

// ---------------------------------------------------------------------------
// Timestamp markers: show a clickable timestamp every ~60s
// ---------------------------------------------------------------------------

const TIMESTAMP_INTERVAL = 60;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  chunks: TranscriptChunk[];
  claims: ClaimDetail[];
  currentTime: number;
  onSeek: (seconds: number) => void;
}

export default function TranscriptPanel({
  chunks,
  claims,
  currentTime,
  onSeek,
}: Props) {
  const tokens = useMemo(() => buildTokens(chunks, claims), [chunks, claims]);

  // Auto-scroll
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeRef = useRef<HTMLSpanElement>(null);
  const lastScrollTime = useRef(0);

  useEffect(() => {
    if (activeRef.current && scrollRef.current) {
      const now = Date.now();
      if (now - lastScrollTime.current < 2000) return;
      lastScrollTime.current = now;

      const container = scrollRef.current;
      const el = activeRef.current;
      const elTop = el.offsetTop - container.offsetTop;
      const elBottom = elTop + el.offsetHeight;
      const scrollTop = container.scrollTop;
      const viewHeight = container.clientHeight;

      if (
        elTop < scrollTop + viewHeight * 0.2 ||
        elBottom > scrollTop + viewHeight * 0.8
      ) {
        container.scrollTo({
          top: elTop - viewHeight * 0.35,
          behavior: "smooth",
        });
      }
    }
  }, [currentTime]);

  // Track which timestamps we've emitted
  let lastTimestampBucket = -1;

  return (
    <div className="rounded-lg border border-zinc-800 relative flex flex-col h-full min-h-0">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-zinc-800 shrink-0">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-500">
          Transcript &middot; {claims.length} claims
        </span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 min-h-0 custom-scrollbar"
      >
        <div className="text-[0.8125rem] leading-[2]">
          {tokens.map((token, i) => {
            if (token.kind === "claim") {
              const claim = token.claim;
              const color =
                CLAIM_TYPE_COLORS[claim.claim_type] || "#71717a";
              return (
                <span
                  key={`c-${claim.claim_id}`}
                  className="inline-flex items-center gap-1 mx-1 align-baseline cursor-pointer"
                  onClick={() => {
                    if (claim.start_ts != null) onSeek(claim.start_ts);
                  }}
                  title={claim.claim_text ?? undefined}
                >
                  <span
                    className="rounded px-1 py-px font-semibold uppercase"
                    style={{
                      backgroundColor: color + "1a",
                      color,
                      fontSize: "0.5625rem",
                      letterSpacing: "0.04em",
                    }}
                  >
                    {claim.claim_type.replace("_", " ")}
                  </span>
                  {claim.player_name && (
                    <span
                      className="font-medium text-zinc-300"
                      style={{ fontSize: "0.6875rem" }}
                    >
                      {claim.player_name}
                    </span>
                  )}
                </span>
              );
            }

            // Word token
            const ts = token.ts;
            const isActive =
              currentTime >= ts &&
              (i + 1 < tokens.length
                ? tokens[i + 1].kind === "word"
                  ? currentTime < (tokens[i + 1] as WordToken).ts
                  : true
                : true);

            // Periodic timestamp marker
            const bucket = Math.floor(ts / TIMESTAMP_INTERVAL);
            let showTimestamp = false;
            if (bucket > lastTimestampBucket) {
              lastTimestampBucket = bucket;
              showTimestamp = true;
            }

            return (
              <span key={`w-${i}`}>
                {showTimestamp && (
                  <button
                    onClick={() => onSeek(ts)}
                    className="inline-block mx-1 align-baseline transition-colors hover:text-orange-400"
                    style={{
                      color: "#52525b",
                      fontSize: "0.625rem",
                      fontVariantNumeric: "tabular-nums",
                      verticalAlign: "baseline",
                    }}
                    title={`Seek to ${formatTimestamp(ts)}`}
                  >
                    {formatTimestamp(ts)}
                  </button>
                )}
                <span
                  ref={isActive ? activeRef : undefined}
                  className="transition-colors duration-300"
                  style={{
                    color: isActive ? "#e4e4e7" : "#71717a",
                    backgroundColor: isActive
                      ? "rgba(251,146,60,0.15)"
                      : "transparent",
                    borderRadius: isActive ? "2px" : undefined,
                    padding: isActive ? "1px 2px" : undefined,
                  }}
                >
                  {token.text}{" "}
                </span>
              </span>
            );
          })}
        </div>
      </div>

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-8 rounded-b-lg pointer-events-none"
        style={{
          background: "linear-gradient(to top, var(--background), transparent)",
        }}
      />
    </div>
  );
}
