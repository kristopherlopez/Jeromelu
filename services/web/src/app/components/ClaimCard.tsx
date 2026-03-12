"use client";

import { forwardRef } from "react";
import type { ClaimDetail } from "@/lib/types";

const TYPE_COLORS: Record<string, string> = {
  buy: "#22c55e",
  sell: "#ef4444",
  hold: "#eab308",
  captain: "#f97316",
  avoid: "#991b1b",
  breakout: "#06b6d4",
  matchup_edge: "#a855f7",
};

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

interface Props {
  claim: ClaimDetail;
  isActive: boolean;
  onSeek: (seconds: number) => void;
}

const ClaimCard = forwardRef<HTMLDivElement, Props>(
  ({ claim, isActive, onSeek }, ref) => {
    const color = TYPE_COLORS[claim.claim_type] || "#71717a";
    const earliestTs = claim.chunks
      .map((c) => c.start_ts)
      .filter((t): t is number => t !== null)
      .sort((a, b) => a - b)[0];

    return (
      <div
        ref={ref}
        className="rounded-lg border p-3 transition-all duration-200"
        style={{
          borderColor: isActive ? "var(--tigers-orange)" : "rgba(255,255,255,0.08)",
          borderLeftWidth: isActive ? 3 : 1,
          backgroundColor: isActive
            ? "rgba(245, 130, 32, 0.08)"
            : "rgba(255,255,255,0.02)",
        }}
      >
        {/* Top row: type pill, player name, timestamp */}
        <div className="mb-1.5 flex items-center gap-2">
          <span
            className="rounded px-1.5 py-0.5 text-xs font-semibold uppercase"
            style={{ backgroundColor: color + "22", color }}
          >
            {claim.claim_type.replace("_", " ")}
          </span>
          {claim.player_name && (
            <span className="text-sm font-medium text-zinc-200">
              {claim.player_name}
            </span>
          )}
          <span className="flex-1" />
          {earliestTs !== undefined && (
            <button
              onClick={() => onSeek(earliestTs)}
              className="rounded px-1.5 py-0.5 text-xs font-mono cursor-pointer hover:bg-zinc-700"
              style={{ color: "var(--tigers-orange)" }}
            >
              {formatTimestamp(earliestTs)} →
            </button>
          )}
        </div>

        {/* Claim text */}
        {claim.claim_text && (
          <p className="mb-1.5 text-sm leading-snug text-zinc-400 italic">
            &ldquo;{claim.claim_text}&rdquo;
          </p>
        )}

        {/* Strength bar + polarity */}
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          {claim.strength !== null && (
            <div className="flex items-center gap-1.5">
              <div className="h-1.5 w-16 overflow-hidden rounded-full bg-zinc-800">
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${(claim.strength ?? 0) * 100}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
              <span>{claim.strength?.toFixed(1)}</span>
            </div>
          )}
          {claim.polarity !== null && (
            <span>
              polarity:{" "}
              <span
                style={{
                  color:
                    claim.polarity > 0
                      ? "#22c55e"
                      : claim.polarity < 0
                        ? "#ef4444"
                        : "#71717a",
                }}
              >
                {claim.polarity > 0 ? "+" : ""}
                {claim.polarity.toFixed(1)}
              </span>
            </span>
          )}
        </div>
      </div>
    );
  }
);

ClaimCard.displayName = "ClaimCard";
export default ClaimCard;
