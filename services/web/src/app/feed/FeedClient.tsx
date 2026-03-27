"use client";

import { useState, useMemo, useRef, useCallback, useEffect } from "react";
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
  SendHorizonal,
} from "lucide-react";
import { apiPost } from "@/lib/api";
import FeedItemCard from "./FeedItemCard";
import type {
  FeedItem,
  FeedItemType,
  FeedAskRequest,
  FeedAskResponse,
  TemperatureMode,
} from "./feed-data";

const ICON_KEY: { icon: typeof Eye; label: string; color: string }[] = [
  { icon: Eye, label: "watching", color: "rgb(113, 113, 122)" },
  { icon: TrendingUp, label: "signal", color: "var(--tigers-orange)" },
  { icon: Brain, label: "thinking", color: "rgb(168, 85, 247)" },
  { icon: Target, label: "prediction", color: "rgb(59, 130, 246)" },
  { icon: Zap, label: "action", color: "var(--tigers-orange)" },
  { icon: RotateCcw, label: "review", color: "rgb(234, 179, 8)" },
  { icon: Settings, label: "sys", color: "rgb(63, 63, 70)" },
  { icon: MessageCircle, label: "question", color: "rgb(59, 130, 246)" },
  { icon: BotMessageSquare, label: "answer", color: "var(--tigers-orange)" },
];

type FilterKey = "all" | "thoughts" | "actions" | "predictions" | "chat";

const FILTER_TYPES: Record<FilterKey, FeedItemType[] | null> = {
  all: null,
  thoughts: ["watching", "signal", "thinking", "review"],
  actions: ["action", "sys"],
  predictions: ["prediction"],
  chat: ["question", "answer"],
};

const TEMP_LABELS: { key: TemperatureMode; label: string }[] = [
  { key: "straight", label: "Straight" },
  { key: "sharp", label: "Sharp" },
  { key: "roast", label: "Roast" },
];

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
      <span className="font-mono text-[10px] uppercase tracking-widest text-zinc-500">
        {label}
      </span>
      <div className="flex-1 border-t border-zinc-800/30" />
    </div>
  );
}

export default function FeedClient({ items: serverItems }: { items: FeedItem[] }) {
  const [items, setItems] = useState<FeedItem[]>(serverItems);
  const [filter, setFilter] = useState<FilterKey>("all");
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [temperature, setTemperature] = useState<TemperatureMode>("sharp");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  // Scroll to top when new items are added
  useEffect(() => {
    if (scrollRef.current && loading === false) {
      scrollRef.current.scrollTop = 0;
    }
  }, [items.length, loading]);

  const submit = useCallback(
    async (question: string) => {
      if (!question.trim() || loading) return;

      setError(null);
      setInput("");
      setLoading(true);

      // Optimistic question item
      const tempQuestion: FeedItem = {
        id: `temp-q-${Date.now()}`,
        type: "question",
        text: question.trim(),
        timestamp: new Date().toISOString(),
      };
      setItems((prev) => [tempQuestion, ...prev]);

      try {
        const res = await apiPost<FeedAskResponse, FeedAskRequest>("/api/feed/ask", {
          question: question.trim(),
          temperature,
        });

        // Replace optimistic question with real items
        setItems((prev) => [
          res.answer_item,
          res.question_item,
          ...prev.filter((i) => i.id !== tempQuestion.id),
        ]);
      } catch {
        setError("Something broke. Even I have bad days. Try again.");
        // Remove optimistic question
        setItems((prev) => prev.filter((i) => i.id !== tempQuestion.id));
      } finally {
        setLoading(false);
        inputRef.current?.focus();
      }
    },
    [loading, temperature]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit(input);
    }
  };

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-3xl flex-col px-4 pt-14">
      {/* Filter bar */}
      <div className="mb-4 flex items-center gap-3 border-b border-zinc-800/30 pb-3">
        {(Object.keys(FILTER_TYPES) as FilterKey[]).map((key) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className="font-mono text-[11px] uppercase tracking-wider transition-colors"
            style={{
              color: filter === key ? "var(--tigers-orange)" : "rgb(113, 113, 122)",
            }}
          >
            {key}
          </button>
        ))}
        <span className="ml-auto font-mono text-[11px] text-zinc-500">
          {filtered.length} entries
        </span>
      </div>

      {/* Icon key */}
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1">
        {ICON_KEY.map(({ icon: Icon, label, color }) => (
          <span key={label} className="flex items-center gap-1.5">
            <Icon size={11} style={{ color }} />
            <span className="font-mono text-[10px] text-zinc-500">{label}</span>
          </span>
        ))}
      </div>

      {/* Stream — scrollable */}
      <div ref={scrollRef} className="custom-scrollbar flex-1 overflow-y-auto pb-4">
        {filtered.length === 0 && !loading ? (
          <div className="py-20 text-center font-mono text-xs text-zinc-500">
            &gt; waiting for input...
          </div>
        ) : (
          <div>
            {/* Thinking indicator */}
            {loading && (
              <div className="flex gap-0 py-1.5">
                <div className="w-10 shrink-0" />
                <div className="w-8 shrink-0 flex items-center justify-center" style={{ height: 22 }}>
                  <BotMessageSquare size={13} style={{ color: "var(--tigers-orange)" }} />
                </div>
                <span className="animate-pulse text-[13px] text-zinc-500">thinking...</span>
              </div>
            )}

            {error && !loading && (
              <div className="flex gap-0 py-1.5">
                <div className="w-10 shrink-0" />
                <div className="w-8 shrink-0" />
                <span className="text-[13px] text-red-400">{error}</span>
              </div>
            )}

            {itemsWithDividers.map((entry, i) =>
              entry.type === "divider" ? (
                <DayDivider key={`div-${entry.label}`} label={entry.label} />
              ) : (
                <FeedItemCard key={entry.item.id} item={entry.item} />
              )
            )}
            {filtered.length > 0 && (
              <div className="mt-4 pt-4 border-t border-zinc-800/20 text-center font-mono text-[11px] text-zinc-500">
                &gt; end of stream. watching for new intel...
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chat input */}
      <div className="border-t border-zinc-800/30 pb-4 pt-3">
        {/* Temperature toggle */}
        <div className="mb-2 flex items-center gap-1">
          <span className="mr-2 font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            tone
          </span>
          {TEMP_LABELS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTemperature(key)}
              className="rounded px-2 py-0.5 font-mono text-[11px] transition-colors"
              style={{
                color: temperature === key ? "var(--tigers-orange)" : "rgb(113, 113, 122)",
                backgroundColor:
                  temperature === key ? "rgba(245, 130, 32, 0.1)" : "transparent",
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Input row */}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask me anything about SuperCoach..."
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-sm text-zinc-200 placeholder-zinc-600 outline-none transition-colors focus:border-zinc-600 disabled:opacity-50"
            style={{ minHeight: "2.5rem", maxHeight: "8rem" }}
          />
          <button
            onClick={() => submit(input)}
            disabled={!input.trim() || loading}
            className="flex h-10 w-10 items-center justify-center rounded border border-zinc-800 transition-colors hover:border-zinc-600 disabled:opacity-30"
            style={{ color: input.trim() ? "var(--tigers-orange)" : "rgb(63, 63, 70)" }}
          >
            <SendHorizonal size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
