"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { ClaimDetail } from "@/lib/types";
import { CLAIM_TYPE_COLORS } from "@/lib/constants";
import ClaimCard from "./ClaimCard";

interface Props {
  claims: ClaimDetail[];
  activeClaimId: string | null;
  onSeek: (seconds: number) => void;
}

export default function ClaimsList({ claims, activeClaimId, onSeek }: Props) {
  const [filter, setFilter] = useState<string | null>(null);
  const cardRefs = useRef<Map<string, HTMLDivElement>>(new Map());

  const types = useMemo(() => {
    const set = new Set(claims.map((c) => c.claim_type));
    return Array.from(set).sort();
  }, [claims]);

  const filtered = filter
    ? claims.filter((c) => c.claim_type === filter)
    : claims;

  // Auto-scroll active claim into view
  useEffect(() => {
    if (!activeClaimId) return;
    const el = cardRefs.current.get(activeClaimId);
    el?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [activeClaimId]);

  return (
    <div className="flex h-full flex-col">
      {/* Filter pills */}
      <div className="mb-3 flex flex-wrap gap-1.5">
        <button
          onClick={() => setFilter(null)}
          className="rounded-full px-2.5 py-1 text-xs font-medium cursor-pointer transition-colors"
          style={{
            backgroundColor: !filter ? "var(--accent-border)" : "rgba(255,255,255,0.05)",
            color: !filter ? "var(--accent)" : "var(--foreground-secondary)",
            border: `1px solid ${!filter ? "var(--accent-glow)" : "transparent"}`,
          }}
        >
          All ({claims.length})
        </button>
        {types.map((t) => {
          const color = CLAIM_TYPE_COLORS[t] || "var(--foreground-muted)";
          const active = filter === t;
          const count = claims.filter((c) => c.claim_type === t).length;
          return (
            <button
              key={t}
              onClick={() => setFilter(active ? null : t)}
              className="rounded-full px-2.5 py-1 text-xs font-medium uppercase cursor-pointer transition-colors"
              style={{
                backgroundColor: active ? color + "33" : "rgba(255,255,255,0.05)",
                color: active ? color : "var(--foreground-secondary)",
                border: `1px solid ${active ? color + "55" : "transparent"}`,
              }}
            >
              {t.replace("_", " ")} ({count})
            </button>
          );
        })}
      </div>

      {/* Scrollable claims */}
      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {filtered.map((claim) => (
          <ClaimCard
            key={claim.claim_id}
            ref={(el) => {
              if (el) cardRefs.current.set(claim.claim_id, el);
              else cardRefs.current.delete(claim.claim_id);
            }}
            claim={claim}
            isActive={claim.claim_id === activeClaimId}
            onSeek={onSeek}
          />
        ))}
        {filtered.length === 0 && (
          <div className="py-12 text-center">
            <p className="text-sm" style={{ color: "var(--foreground-ghost)" }}>
              {filter
                ? `No claims of type "${filter.replace("_", " ")}"`
                : "No claims extracted yet"}
            </p>
            {!filter && (
              <p className="mt-1 text-xs" style={{ color: "var(--foreground-ghost)" }}>
                Claims will appear here once this source is processed.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
