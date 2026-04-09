"use client";

import { useState } from "react";
import Link from "next/link";
import type {
  InsightListItem,
  ArticleType,
} from "./insights-data";
import {
  ARTICLE_TYPE_LABELS,
} from "./insights-data";

const ALL_TYPES: ArticleType[] = [
  "tips", "totw", "trades", "captains", "stocks", "consensus",
];

const TYPE_COLORS: Record<ArticleType, { color: string; bg: string; border: string }> = {
  tips: { color: "var(--accent)", bg: "var(--accent-bg)", border: "var(--accent-border)" },
  totw: { color: "var(--teal)", bg: "var(--teal-bg)", border: "var(--teal-border)" },
  trades: { color: "var(--slate)", bg: "var(--slate-bg)", border: "var(--slate-border)" },
  captains: { color: "var(--lilac)", bg: "var(--lilac-bg)", border: "rgba(168,152,200,0.22)" },
  stocks: { color: "var(--ochre)", bg: "var(--ochre-bg)", border: "var(--ochre-border)" },
  consensus: { color: "var(--terracotta)", bg: "var(--terracotta-bg)", border: "rgba(184,92,56,0.22)" },
};

function TypeBadge({ type, small }: { type: ArticleType; small?: boolean }) {
  const c = TYPE_COLORS[type];
  return (
    <span
      style={{
        display: "inline-block",
        fontSize: small ? "10px" : "11px",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        padding: small ? "0.1rem 0.4rem" : "0.15rem 0.5rem",
        borderRadius: "3px",
        background: c.bg,
        color: c.color,
        border: `1px solid ${c.border}`,
      }}
    >
      {ARTICLE_TYPE_LABELS[type]}
    </span>
  );
}

function FilterButton({
  label,
  active,
  onClick,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="transition-colors"
      style={{
        padding: "0.35rem 0.85rem",
        fontSize: 13,
        fontWeight: 500,
        color: active ? "var(--accent)" : "var(--foreground-muted)",
        background: active ? "var(--accent-bg)" : "var(--surface)",
        border: `1px solid ${active ? "var(--accent-border)" : "var(--border)"}`,
        borderRadius: 4,
        cursor: "pointer",
      }}
    >
      {label}
    </button>
  );
}

function ArticleCard({ item }: { item: InsightListItem }) {
  const date = new Date(item.created_at);
  const timeAgo = formatTimeAgo(date);

  return (
    <Link
      href={`/insights/${item.kb_id}`}
      className="transition-colors"
      style={{
        display: "block",
        padding: "1rem 1.25rem",
        background: "var(--surface)",
        textDecoration: "none",
        color: "inherit",
      }}
      onMouseEnter={(e) =>
        (e.currentTarget.style.background = "var(--surface-hover)")
      }
      onMouseLeave={(e) =>
        (e.currentTarget.style.background = "var(--surface)")
      }
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "0.6rem",
          marginBottom: "0.4rem",
        }}
      >
        <TypeBadge type={item.article_type} small />
        <span
          style={{
            fontFamily: "var(--font-geist-mono)",
            fontSize: "11px",
            color: "var(--foreground-faint)",
          }}
        >
          Round {item.effective_round} &middot; {timeAgo}
        </span>
      </div>

      <div
        style={{
          fontSize: "14px",
          fontWeight: 500,
          color: "var(--foreground)",
          marginBottom: "0.25rem",
        }}
      >
        {item.title}
      </div>

      <p
        style={{
          fontSize: "13px",
          color: "var(--foreground-muted)",
          margin: 0,
          lineHeight: 1.5,
          overflow: "hidden",
          textOverflow: "ellipsis",
          display: "-webkit-box",
          WebkitLineClamp: 2,
          WebkitBoxOrient: "vertical",
        }}
      >
        {item.summary}
      </p>
    </Link>
  );
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diff = now.getTime() - date.getTime();
  const hours = Math.floor(diff / (1000 * 60 * 60));
  if (hours < 1) return "just now";
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days === 1) return "yesterday";
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

interface InsightsClientProps {
  items: InsightListItem[];
}

export default function InsightsClient({ items }: InsightsClientProps) {
  const [filter, setFilter] = useState<ArticleType | null>(null);

  const filtered = filter
    ? items.filter((i) => i.article_type === filter)
    : items;

  // Group by round
  const byRound = new Map<number, InsightListItem[]>();
  for (const item of filtered) {
    const round = item.effective_round;
    if (!byRound.has(round)) byRound.set(round, []);
    byRound.get(round)!.push(item);
  }
  const rounds = [...byRound.keys()].sort((a, b) => b - a);

  return (
    <div className="min-h-screen">
      <div className="mx-auto max-w-5xl px-6">
        {/* Header */}
        <div className="pt-10 pb-6">
          <h1
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontSize: "2.2rem",
              fontWeight: 700,
              color: "var(--foreground)",
              marginBottom: "0.25rem",
            }}
          >
            The Analysis
          </h1>
          <p
            style={{
              fontSize: 14,
              color: "var(--foreground-muted)",
              marginBottom: "1rem",
            }}
          >
            Tips, picks, and consensus. Every round, every angle.
          </p>
          <p
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              fontStyle: "italic",
              fontSize: "1.05rem",
              color: "var(--accent)",
              paddingLeft: "1rem",
              borderLeft: "2px solid var(--accent-border)",
            }}
          >
            &ldquo;I watch everything. I read everyone. Here&rsquo;s what matters.&rdquo;
          </p>
        </div>

        {/* Filter bar */}
        <div className="flex flex-wrap gap-2 mb-6">
          <FilterButton
            label="All"
            active={filter === null}
            onClick={() => setFilter(null)}
          />
          {ALL_TYPES.map((t) => (
            <FilterButton
              key={t}
              label={ARTICLE_TYPE_LABELS[t]}
              active={filter === t}
              onClick={() => setFilter(filter === t ? null : t)}
            />
          ))}
        </div>

        {/* Articles */}
        {filtered.length === 0 ? (
          <div
            style={{
              textAlign: "center",
              padding: "4rem 1.5rem",
              color: "var(--foreground-muted)",
            }}
          >
            <p
              style={{
                fontSize: "15px",
                fontWeight: 500,
                margin: "0 0 0.5rem 0",
                color: "var(--foreground-secondary)",
              }}
            >
              No analysis yet
            </p>
            <p style={{ fontSize: "13px", margin: 0, color: "var(--foreground-faint)" }}>
              Articles will appear here once Jaromelu starts publishing.
            </p>
          </div>
        ) : (
          <div className="pb-12">
            {rounds.map((round) => (
              <div key={round} style={{ marginBottom: "1.5rem" }}>
                <div
                  style={{
                    fontSize: "11px",
                    fontWeight: 600,
                    letterSpacing: "0.06em",
                    textTransform: "uppercase",
                    color: "var(--foreground-faint)",
                    padding: "0 0 0.5rem 0.25rem",
                  }}
                >
                  Round {round}
                </div>
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    gap: 1,
                    background: "var(--border)",
                    border: "1px solid var(--border)",
                    borderRadius: 8,
                    overflow: "hidden",
                  }}
                >
                  {byRound.get(round)!.map((item) => (
                    <ArticleCard key={item.kb_id} item={item} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
