"use client";

import { useState, useMemo } from "react";
import {
  Eye,
  TrendingUp,
  Brain,
  Target,
  Zap,
  RotateCcw,
  Settings,
} from "lucide-react";
import FeedItemCard from "./FeedItemCard";
import type { FeedItem, FeedItemType } from "./feed-data";

const ICON_KEY: { icon: typeof Eye; label: string; color: string }[] = [
  { icon: Eye, label: "watching", color: "rgb(113, 113, 122)" },
  { icon: TrendingUp, label: "signal", color: "var(--tigers-orange)" },
  { icon: Brain, label: "thinking", color: "rgb(168, 85, 247)" },
  { icon: Target, label: "prediction", color: "rgb(59, 130, 246)" },
  { icon: Zap, label: "action", color: "var(--tigers-orange)" },
  { icon: RotateCcw, label: "review", color: "rgb(234, 179, 8)" },
  { icon: Settings, label: "sys", color: "rgb(63, 63, 70)" },
];

type FilterKey = "all" | "thoughts" | "actions" | "predictions";

const FILTER_TYPES: Record<FilterKey, FeedItemType[] | null> = {
  all: null,
  thoughts: ["reaction", "narrative_shift", "reasoning", "review"],
  actions: ["action", "system"],
  predictions: ["prediction"],
};

function getDayLabel(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const itemDay = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const diffDays = Math.floor((today.getTime() - itemDay.getTime()) / 86_400_000);

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  return date.toLocaleDateString("en-AU", {
    weekday: "short",
    day: "numeric",
    month: "short",
  }).toLowerCase();
}

function DayDivider({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 py-2">
      <div className="flex-1 border-t border-zinc-800/30" />
      <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-700">
        {label}
      </span>
      <div className="flex-1 border-t border-zinc-800/30" />
    </div>
  );
}

export default function FeedClient({ items }: { items: FeedItem[] }) {
  const [filter, setFilter] = useState<FilterKey>("all");

  const filtered = useMemo(() => {
    const types = FILTER_TYPES[filter];
    if (!types) return items;
    return items.filter((item) => types.includes(item.type));
  }, [items, filter]);

  const itemsWithDividers = useMemo(() => {
    const result: ({ type: "divider"; label: string } | { type: "item"; item: FeedItem })[] = [];
    let lastDay = "";

    for (const item of filtered) {
      const day = getDayLabel(item.timestamp);
      if (day !== lastDay) {
        result.push({ type: "divider", label: day });
        lastDay = day;
      }
      result.push({ type: "item", item });
    }

    return result;
  }, [filtered]);

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 pt-14">
      {/* Filter bar — minimal */}
      <div className="mb-4 flex items-center gap-3 border-b border-zinc-800/30 pb-3">
        {(Object.keys(FILTER_TYPES) as FilterKey[]).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className="font-mono text-[11px] uppercase tracking-wider transition-colors"
            style={{
              color: filter === key ? "var(--tigers-orange)" : "rgb(63, 63, 70)",
            }}
          >
            {key}
          </button>
        ))}
        <span className="ml-auto font-mono text-[11px] text-zinc-800">
          {filtered.length} entries
        </span>
      </div>

      {/* Icon key */}
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1">
        {ICON_KEY.map(({ icon: Icon, label, color }) => (
          <span key={label} className="flex items-center gap-1.5">
            <Icon size={11} style={{ color }} />
            <span className="font-mono text-[10px] text-zinc-600">{label}</span>
          </span>
        ))}
      </div>

      {/* Stream */}
      {filtered.length === 0 ? (
        <div className="py-20 text-center font-mono text-xs text-zinc-600">
          &gt; waiting for input...
        </div>
      ) : (
        <div>
          {itemsWithDividers.map((entry, i) =>
            entry.type === "divider" ? (
              <DayDivider key={`div-${entry.label}`} label={entry.label} />
            ) : (
              <FeedItemCard key={entry.item.id} item={entry.item} />
            )
          )}
          <div className="mt-4 pt-4 border-t border-zinc-800/20 text-center font-mono text-[11px] text-zinc-700">
            &gt; end of stream. watching for new intel...
          </div>
        </div>
      )}
    </div>
  );
}
