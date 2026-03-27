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
  endTs: number;
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
  const sorted = claims
    .filter((c) => c.start_ts != null)
    .sort((a, b) => a.start_ts! - b.start_ts!);

  const tokens: Token[] = [];
  let claimIdx = 0;

  for (const chunk of chunks) {
    const ts = chunk.start_ts ?? 0;
    const endTs = chunk.end_ts ?? ts;

    // Insert any claim markers that start before/at this chunk
    while (claimIdx < sorted.length && sorted[claimIdx].start_ts! <= ts) {
      tokens.push({ kind: "claim", claim: sorted[claimIdx] });
      claimIdx++;
    }

    const text = chunkText(chunk).trim();
    if (text) {
      tokens.push({ kind: "word", text, ts, endTs });
    }
  }

  while (claimIdx < sorted.length) {
    tokens.push({ kind: "claim", claim: sorted[claimIdx] });
    claimIdx++;
  }

  return tokens;
}

/** Find the claim (if any) that covers a given timestamp */
function findCoveringClaim(
  ts: number,
  claims: ClaimDetail[]
): ClaimDetail | null {
  for (const c of claims) {
    if (c.start_ts != null && c.end_ts != null && ts >= c.start_ts && ts < c.end_ts) {
      return c;
    }
  }
  return null;
}

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
  const sortedClaims = useMemo(
    () => claims.filter((c) => c.start_ts != null && c.end_ts != null),
    [claims]
  );

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

            // Word token — each corresponds to one transcript segment/chunk
            const { ts, endTs } = token;
            const isActive = currentTime >= ts && currentTime < endTs;

            // Check if this chunk falls within a claim's range
            const coveringClaim = findCoveringClaim(ts, sortedClaims);
            const claimColor = coveringClaim
              ? CLAIM_TYPE_COLORS[coveringClaim.claim_type] || "#71717a"
              : null;

            // Determine styling based on state
            let textColor: string;
            let bgColor: string;
            if (isActive) {
              textColor = "#f4f4f5";
              bgColor = "rgba(251,146,60,0.18)";
            } else if (coveringClaim) {
              textColor = "#d4d4d8";
              bgColor = claimColor + "12";
            } else {
              textColor = "#71717a";
              bgColor = "transparent";
            }

            return (
              <span
                key={`w-${i}`}
                ref={isActive ? activeRef : undefined}
                className="cursor-pointer transition-colors duration-300"
                onClick={() => onSeek(ts)}
                style={{
                  color: textColor,
                  backgroundColor: bgColor,
                  borderRadius: isActive || coveringClaim ? "2px" : undefined,
                  padding: isActive || coveringClaim ? "1px 3px" : undefined,
                }}
              >
                {token.text}{" "}
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
