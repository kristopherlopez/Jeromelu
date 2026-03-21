"use client";

import {
  Eye,
  TrendingUp,
  Brain,
  Target,
  Zap,
  RotateCcw,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { FeedItem, FeedItemType } from "./feed-data";

const TYPE_CONFIG: Record<
  FeedItemType,
  { icon: LucideIcon; label: string; color: string }
> = {
  reaction: { icon: Eye, label: "watching", color: "rgb(113, 113, 122)" },
  narrative_shift: { icon: TrendingUp, label: "signal", color: "var(--tigers-orange)" },
  reasoning: { icon: Brain, label: "thinking", color: "rgb(168, 85, 247)" },
  prediction: { icon: Target, label: "prediction", color: "rgb(59, 130, 246)" },
  action: { icon: Zap, label: "action", color: "var(--tigers-orange)" },
  review: { icon: RotateCcw, label: "review", color: "rgb(234, 179, 8)" },
  system: { icon: Settings, label: "sys", color: "rgb(63, 63, 70)" },
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
      style={{ color: "var(--tigers-orange)" }}
    >
      {name}
    </span>
  );
}

function renderTextWithPlayers(text: string, players?: { name: string }[]) {
  if (!players || players.length === 0) return text;

  // Build a regex that matches any player name
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
  if (status === "pending") return <span className="text-zinc-500"> [pending]</span>;
  if (status === "correct") return <span style={{ color: "rgb(34, 197, 94)" }}> [correct]</span>;
  return <span style={{ color: "rgb(239, 68, 68)" }}> [wrong]</span>;
}

export default function FeedItemCard({ item }: { item: FeedItem }) {
  const config = TYPE_CONFIG[item.type];
  const Icon = config.icon;
  const isSystem = item.type === "system";
  const isAction = item.type === "action";

  return (
    <div
      className={`group flex gap-0 py-1.5 transition-colors hover:bg-white/[0.02] ${
        isSystem ? "opacity-50" : ""
      }`}
    >
      {/* Timestamp gutter */}
      <div className="w-10 shrink-0 flex items-center justify-end" style={{ height: 22 }}>
        <span className="font-mono text-[11px] text-zinc-700">{timeAgo(item.timestamp)}</span>
      </div>

      {/* Type icon */}
      <div className="w-8 shrink-0 flex items-center justify-center" style={{ height: 22 }}>
        <Icon size={13} style={{ color: config.color }} />
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        {isSystem ? (
          <p className="font-mono text-xs text-zinc-600">{item.text}</p>
        ) : (
          <>
            {/* Action prefix */}
            {isAction && (
              <span
                className="font-mono text-xs font-bold mr-1.5"
                style={{ color: "var(--tigers-orange)" }}
              >
                &gt;
              </span>
            )}
            <span className="text-[13px] leading-relaxed text-zinc-300">
              {renderTextWithPlayers(item.text, item.players)}
              {item.prediction && <PredictionStatus status={item.prediction.status} />}
            </span>

            {/* Source attribution */}
            {item.source && (
              <span className="ml-2 text-[11px] text-zinc-600 hover:text-zinc-400 cursor-pointer transition-colors">
                via {item.source.creator || item.source.title}
              </span>
            )}

            {/* Review outcome inline */}
            {item.prediction?.outcome && (
              <span className="ml-2 font-mono text-[11px] text-zinc-600 italic">
                — {item.prediction.outcome}
              </span>
            )}
          </>
        )}
      </div>
    </div>
  );
}
