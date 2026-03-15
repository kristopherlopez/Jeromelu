"use client";

import { useEffect, useMemo, useRef } from "react";
import type { TranscriptChunk, ClaimDetail } from "@/lib/types";
import { CLAIM_TYPE_COLORS } from "@/lib/constants";

/** Get display text for a chunk, preferring clean_text over raw_text. */
function chunkText(chunk: TranscriptChunk): string {
  return chunk.clean_text ?? chunk.raw_text;
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface ClaimSpan {
  text: string;
  isClaim: boolean;
  ts: number | null;
  claim?: ClaimDetail;
  /** Character offset of this span within the full chunk text */
  charOffset: number;
}

interface Sentence {
  text: string;
  estimatedStart: number;
  estimatedEnd: number;
}

/** Split a non-claim span's text into sentences with interpolated timestamps. */
function splitIntoSentences(
  spanText: string,
  spanCharOffset: number,
  chunkLen: number,
  chunkStart: number,
  chunkEnd: number
): Sentence[] {
  const parts = spanText.split(/(?<=\.)\s+/);
  const sentences: Sentence[] = [];
  let offset = spanCharOffset;

  for (const part of parts) {
    if (!part) continue;
    const startFrac = offset / chunkLen;
    const endFrac = (offset + part.length) / chunkLen;
    sentences.push({
      text: part + (part.endsWith(".") ? " " : ""),
      estimatedStart: chunkStart + startFrac * (chunkEnd - chunkStart),
      estimatedEnd: chunkStart + endFrac * (chunkEnd - chunkStart),
    });
    offset += part.length + 1; // +1 for the split whitespace
  }

  return sentences;
}

/**
 * Split a chunk's text into claim / non-claim spans by matching claim_text
 * excerpts within the chunk.
 */
function splitChunkByClaims(
  chunk: TranscriptChunk,
  claims: ClaimDetail[]
): ClaimSpan[] {
  const relevant = claims.filter((c) => {
    if (c.start_ts == null || chunk.start_ts == null || chunk.end_ts == null)
      return false;
    return c.start_ts >= chunk.start_ts && c.start_ts < chunk.end_ts;
  });

  if (relevant.length === 0) {
    return [{ text: chunkText(chunk), isClaim: false, ts: chunk.start_ts, charOffset: 0 }];
  }

  const chunkLower = chunkText(chunk).toLowerCase();
  const matches: { start: number; end: number; ts: number | null; claim: ClaimDetail }[] = [];

  for (const claim of relevant) {
    if (!claim.claim_text) continue;

    // Strip "Player Name —" prefix for matching
    let search = claim.claim_text;
    const dashIdx = search.indexOf("\u2014");
    if (dashIdx !== -1 && dashIdx < 40) {
      search = search.slice(dashIdx + 1).trim();
    }

    const key = search.slice(0, 80).toLowerCase().replace(/[.,!?]/g, "");
    const words = key.split(/\s+/).filter(Boolean);
    let bestPos = -1;

    for (let len = Math.min(words.length, 8); len >= 3; len--) {
      if (bestPos !== -1) break;
      for (let i = 0; i <= words.length - len; i++) {
        const phrase = words.slice(i, i + len).join(" ");
        const pos = chunkLower.indexOf(phrase);
        if (pos !== -1) {
          bestPos = pos;
          break;
        }
      }
    }

    if (bestPos !== -1) {
      let start = bestPos;
      let end = Math.min(bestPos + search.length, chunkText(chunk).length);

      const prevPeriod = chunkText(chunk).lastIndexOf(". ", start);
      if (prevPeriod !== -1 && start - prevPeriod < 80) {
        start = prevPeriod + 2;
      }
      const nextPeriod = chunkText(chunk).indexOf(". ", end - 10);
      if (nextPeriod !== -1 && nextPeriod - end < 80) {
        end = nextPeriod + 1;
      }

      matches.push({ start, end, ts: claim.start_ts, claim });
    }
  }

  if (matches.length === 0) {
    return [{ text: chunkText(chunk), isClaim: false, ts: chunk.start_ts, charOffset: 0 }];
  }

  // Sort and merge overlapping (keep first claim reference)
  matches.sort((a, b) => a.start - b.start);
  const merged: typeof matches = [matches[0]];
  for (let i = 1; i < matches.length; i++) {
    const prev = merged[merged.length - 1];
    if (matches[i].start <= prev.end) {
      prev.end = Math.max(prev.end, matches[i].end);
    } else {
      merged.push(matches[i]);
    }
  }

  const spans: ClaimSpan[] = [];
  let cursor = 0;
  for (const m of merged) {
    if (m.start > cursor) {
      spans.push({ text: chunkText(chunk).slice(cursor, m.start), isClaim: false, ts: chunk.start_ts, charOffset: cursor });
    }
    spans.push({ text: chunkText(chunk).slice(m.start, m.end), isClaim: true, ts: m.ts, claim: m.claim, charOffset: m.start });
    cursor = m.end;
  }
  if (cursor < chunkText(chunk).length) {
    spans.push({ text: chunkText(chunk).slice(cursor), isClaim: false, ts: chunk.start_ts, charOffset: cursor });
  }

  return spans;
}

interface Props {
  chunks: TranscriptChunk[];
  claims: ClaimDetail[];
  currentTime: number;
  onSeek: (seconds: number) => void;
}

export default function TranscriptPanel({ chunks, claims, currentTime, onSeek }: Props) {
  const splitChunks = useMemo(
    () => chunks.map((chunk) => ({ chunk, spans: splitChunkByClaims(chunk, claims) })),
    [chunks, claims]
  );

  const claimSpanCount = splitChunks.reduce(
    (n, sc) => n + sc.spans.filter((s) => s.isClaim).length,
    0
  );

  // Track which claim is active based on current video time
  const activeClaimTs = useMemo(() => {
    for (const claim of claims) {
      if (
        claim.start_ts !== null &&
        claim.end_ts !== null &&
        currentTime >= claim.start_ts &&
        currentTime < claim.end_ts
      ) {
        return claim.start_ts;
      }
    }
    return null;
  }, [claims, currentTime]);

  // Auto-scroll to the active sentence
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeSentenceRef = useRef<HTMLSpanElement>(null);
  const lastScrollTime = useRef(0);

  useEffect(() => {
    if (activeSentenceRef.current && scrollRef.current) {
      // Throttle scrolling to avoid jitter
      const now = Date.now();
      if (now - lastScrollTime.current < 1000) return;
      lastScrollTime.current = now;

      const container = scrollRef.current;
      const el = activeSentenceRef.current;
      const elTop = el.offsetTop - container.offsetTop;
      const elBottom = elTop + el.offsetHeight;
      const scrollTop = container.scrollTop;
      const viewHeight = container.clientHeight;

      if (elTop < scrollTop + viewHeight * 0.3 || elBottom > scrollTop + viewHeight * 0.7) {
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
          Transcript &middot; {claimSpanCount} claim regions highlighted
        </span>
      </div>

      <div ref={scrollRef} className="flex-1 overflow-y-auto overflow-x-hidden px-4 py-3 min-h-0 custom-scrollbar">
        {splitChunks.map(({ chunk, spans }, chunkIdx) => (
          <div key={chunk.chunk_id} className="mb-3">
            <span>
              {spans.map((span, i) => {
                if (!span.isClaim) {
                  const chunkStart = chunk.start_ts;
                  const chunkEnd = chunk.end_ts;

                  // If chunk has no timestamps, render plain
                  if (chunkStart == null || chunkEnd == null) {
                    return (
                      <span
                        key={i}
                        className="inline text-[0.8125rem] leading-[1.9]"
                        style={{ color: "#71717a" }}
                      >
                        {span.text}
                      </span>
                    );
                  }

                  const sentences = splitIntoSentences(
                    span.text,
                    span.charOffset,
                    chunkText(chunk).length,
                    chunkStart,
                    chunkEnd
                  );

                  return (
                    <span key={i}>
                      {sentences.map((s, j) => {
                        const isActive =
                          currentTime >= s.estimatedStart &&
                          currentTime < s.estimatedEnd;
                        return (
                          <span
                            key={j}
                            ref={isActive ? activeSentenceRef : undefined}
                            className="inline text-[0.8125rem] leading-[1.9] transition-all duration-300"
                            style={{
                              color: isActive ? "#d4d4d8" : "#71717a",
                              backgroundColor: isActive ? "rgba(251,146,60,0.30)" : "transparent",
                              borderRadius: isActive ? "3px" : undefined,
                              padding: isActive ? "1px 3px" : undefined,
                            }}
                          >
                            {s.text}
                          </span>
                        );
                      })}
                    </span>
                  );
                }

                const claim = span.claim!;
                const color = CLAIM_TYPE_COLORS[claim.claim_type] || "#71717a";
                const isActive = span.ts !== null && span.ts === activeClaimTs;

                return (
                  <span
                    key={i}
                    onClick={() => {
                      if (span.ts !== null) onSeek(span.ts);
                    }}
                    className="inline cursor-pointer rounded transition-all"
                    style={{
                      backgroundColor: isActive
                        ? color + "22"
                        : "rgba(255,255,255,0.03)",
                      border: `1px solid ${isActive ? color + "55" : "rgba(255,255,255,0.06)"}`,
                      padding: "2px 4px",
                      fontSize: "0.8125rem",
                      lineHeight: 1.9,
                      color: isActive ? "#f5f5f5" : "#d4d4d8",
                      WebkitBoxDecorationBreak: "clone",
                      boxDecorationBreak: "clone" as const,
                    }}
                  >
                    {/* Inline label */}
                    <span
                      className="inline-flex items-center gap-1 mr-1.5 align-baseline"
                      style={{ fontSize: "0.6875rem" }}
                    >
                      <span
                        className="rounded px-1 py-px font-semibold uppercase"
                        style={{ backgroundColor: color + "22", color, fontSize: "0.5625rem", letterSpacing: "0.04em" }}
                      >
                        {claim.claim_type.replace("_", " ")}
                      </span>
                      {claim.player_name && (
                        <span className="font-medium text-zinc-300" style={{ fontSize: "0.6875rem" }}>
                          {claim.player_name}
                        </span>
                      )}
                    </span>
                    {span.text}
                  </span>
                );
              })}
            </span>
          </div>
        ))}
      </div>

      {/* Bottom fade */}
      <div
        className="absolute bottom-0 left-0 right-0 h-8 rounded-b-lg pointer-events-none"
        style={{ background: "linear-gradient(to top, var(--background), transparent)" }}
      />
    </div>
  );
}
