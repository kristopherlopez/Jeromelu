"use client";

import {
  Eye,
  TrendingUp,
  Brain,
  Target,
  Zap,
  RotateCcw,
  Settings,
  MessageCircle,
  BotMessageSquare,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { FeedItem, FeedItemType } from "./feed-data";

const TYPE_CONFIG: Record<
  FeedItemType,
  { icon: LucideIcon; label: string; color: string }
> = {
  watching: { icon: Eye, label: "watching", color: "var(--wiki-ink-faint)" },
  signal: { icon: TrendingUp, label: "signal", color: "var(--wiki-accent)" },
  thinking: { icon: Brain, label: "thinking", color: "var(--wiki-purple)" },
  prediction: { icon: Target, label: "prediction", color: "var(--wiki-teal)" },
  action: { icon: Zap, label: "action", color: "var(--wiki-accent)" },
  review: { icon: RotateCcw, label: "review", color: "var(--wiki-amber)" },
  sys: { icon: Settings, label: "sys", color: "var(--wiki-ink-faint)" },
  question: { icon: MessageCircle, label: "question", color: "var(--wiki-teal)" },
  answer: { icon: BotMessageSquare, label: "answer", color: "var(--wiki-accent)" },
};

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

function PlayerInline({ name }: { name: string }) {
  return (
    <span
      className="cursor-pointer font-semibold hover:underline"
      style={{ color: "var(--wiki-accent)" }}
    >
      {name}
    </span>
  );
}

function renderTextWithPlayers(text: string, players?: { name: string }[]) {
  if (!players || players.length === 0) return text;

  const escaped = players.map((p) => p.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const regex = new RegExp(`(${escaped.join("|")})`, "g");
  const parts = text.split(regex);

  return parts.map((part, i) => {
    const isPlayer = players.some((p) => p.name === part);
    if (isPlayer) return <PlayerInline key={i} name={part} />;
    return <span key={i}>{part}</span>;
  });
}

function PredictionStatus({ status }: { status: "pending" | "correct" | "wrong" }) {
  const base = { fontSize: "12px", fontFamily: "var(--font-geist-mono, monospace)", letterSpacing: "0.03em" } as const;
  if (status === "pending") return <span style={{ ...base, color: "var(--wiki-ink-faint)" }}> [pending]</span>;
  if (status === "correct") return <span style={{ ...base, color: "var(--wiki-teal)" }}> [correct]</span>;
  return <span style={{ ...base, color: "var(--red, #9a2020)" }}> [wrong]</span>;
}

export default function FeedItemCard({ item }: { item: FeedItem }) {
  const config = TYPE_CONFIG[item.type];
  const Icon = config.icon;
  const isSystem = item.type === "sys";
  const isAction = item.type === "action";
  const isQuestion = item.type === "question";
  const isAnswer = item.type === "answer";

  return (
    <div
      className={`group flex gap-0 py-2.5 transition-colors ${
        isSystem ? "opacity-50" : ""
      }`}
      style={{
        paddingBottom: isAnswer ? "0.75rem" : undefined,
      }}
    >
      {/* Timestamp gutter */}
      <div className="w-12 shrink-0 flex items-start justify-end" style={{ paddingTop: "0.2rem" }}>
        <span style={{ fontSize: "12px", fontFamily: "var(--font-geist-mono, monospace)", color: "var(--wiki-ink-faint)" }}>{timeAgo(item.timestamp)}</span>
      </div>

      {/* Type icon */}
      <div className="w-8 shrink-0 flex items-start justify-center" style={{ paddingTop: "0.3rem" }}>
        <Icon size={14} style={{ color: config.color }} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {isSystem ? (
          <p style={{ fontSize: "13px", fontFamily: "var(--font-geist-mono, monospace)", color: "var(--wiki-ink-faint)" }}>{item.text}</p>
        ) : isQuestion ? (
          <div>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                fontFamily: "var(--font-geist-mono, monospace)",
                color: item.user?.color || "var(--wiki-teal)",
                marginRight: "0.5rem",
              }}
            >
              {item.user?.name || "Coach"}
            </span>
            <span style={{ fontSize: "15px", lineHeight: 1.65, fontStyle: "italic", fontWeight: 600, color: "var(--wiki-ink)" }}>
              {item.text}
            </span>
          </div>
        ) : isAnswer ? (
          <div>
            <span
              style={{
                fontSize: "12px",
                fontWeight: 700,
                fontFamily: "var(--font-geist-mono, monospace)",
                color: "var(--wiki-accent)",
                marginRight: "0.5rem",
              }}
            >
              Jaromelu
            </span>
            <span style={{ fontSize: "15px", lineHeight: 1.65, color: "var(--wiki-ink)" }}>
              {renderTextWithPlayers(item.text, item.players)}
            </span>
            {item.sources && item.sources.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-2">
                {item.sources.map((s) => (
                  <span
                    key={s.sourceId}
                    style={{ fontSize: "11px", fontFamily: "var(--font-geist-mono, monospace)", color: "var(--wiki-ink-faint)" }}
                  >
                    via {s.creator || s.title}
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            {/* Action prefix */}
            {isAction && (
              <span
                className="font-bold mr-1.5"
                style={{ fontSize: "14px", color: "var(--wiki-accent)" }}
              >
                &gt;
              </span>
            )}
            <span style={{ fontSize: "15px", lineHeight: 1.65, color: "var(--wiki-ink)" }}>
              {renderTextWithPlayers(item.text, item.players)}
              {item.prediction && <PredictionStatus status={item.prediction.status} />}
            </span>

            {/* Single source attribution */}
            {item.source && (
              <span className="ml-2 cursor-pointer transition-colors" style={{ fontSize: "12px", fontFamily: "var(--font-geist-mono, monospace)", color: "var(--wiki-ink-faint)" }}>
                via {item.source.creator || item.source.title}
              </span>
            )}

            {/* Review outcome inline */}
            {item.prediction?.outcome && (
              <span className="ml-2 italic" style={{ fontSize: "12px", color: "var(--wiki-ink-faint)" }}>
                — {item.prediction.outcome}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
