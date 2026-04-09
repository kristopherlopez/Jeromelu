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
} from "lucide-react";
import { apiPost } from "@/lib/api";
import ChatInputBar from "@/app/components/ChatInputBar";
import type { TemperatureMode } from "@/app/components/ChatInputBar";
import FeedItemCard from "./FeedItemCard";
import type {
  FeedItem,
  FeedItemType,
  FeedAskRequest,
  FeedAskResponse,
} from "./feed-data";

const ICON_KEY: { icon: typeof Eye; label: string; color: string }[] = [
  { icon: Eye, label: "watching", color: "var(--wiki-ink-faint)" },
  { icon: TrendingUp, label: "signal", color: "var(--wiki-accent)" },
  { icon: Brain, label: "thinking", color: "var(--wiki-purple)" },
  { icon: Target, label: "prediction", color: "var(--wiki-teal)" },
  { icon: Zap, label: "action", color: "var(--wiki-accent)" },
  { icon: RotateCcw, label: "review", color: "var(--wiki-amber)" },
  { icon: Settings, label: "sys", color: "var(--wiki-ink-faint)" },
  { icon: MessageCircle, label: "question", color: "var(--wiki-teal)" },
  { icon: BotMessageSquare, label: "answer", color: "var(--wiki-accent)" },
];

type FilterKey = "all" | "thoughts" | "actions" | "predictions" | "chat";

const FILTER_TYPES: Record<FilterKey, FeedItemType[] | null> = {
  all: null,
  thoughts: ["watching", "signal", "thinking", "review"],
  actions: ["action", "sys"],
  predictions: ["prediction"],
  chat: ["question", "answer"],
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
    <div className="flex items-center gap-3 py-3">
      <div className="flex-1" style={{ borderTop: "1px solid var(--wiki-border)" }} />
      <span style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--wiki-ink-faint)" }}>
        {label}
      </span>
      <div className="flex-1" style={{ borderTop: "1px solid var(--wiki-border)" }} />
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

  const filtered = useMemo(() => {
    const types = FILTER_TYPES[filter];
    if (!types) return items;
    return items.filter((item) => types.includes(item.type));
  }, [items, filter]);

  const itemsWithDividers = useMemo(() => {
    const chronological = [...filtered].reverse();
    const result: ({ type: "divider"; label: string } | { type: "item"; item: FeedItem })[] = [];
    let lastDay = "";

    for (const item of chronological) {
      const day = getDayLabel(item.timestamp);
      if (day !== lastDay) {
        result.push({ type: "divider", label: day });
        lastDay = day;
      }
      result.push({ type: "item", item });
    }

    return result;
  }, [filtered]);

  // Scroll to bottom when new items are added (Twitch-style)
  useEffect(() => {
    if (scrollRef.current && loading === false) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
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
        user: { name: "You" },
      };
      setItems((prev) => [tempQuestion, ...prev]); // prepend (newest-first in data, reversed for display)

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
      }
    },
    [loading, temperature]
  );

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-5xl flex-col px-6">
        {/* Header — compact, no redundant title */}
        <div className="pt-10 pb-6">
          <div>
            <h1 style={{ fontFamily: "var(--font-serif), Georgia, serif", fontSize: "1.8rem", fontWeight: 600, color: "var(--wiki-ink)", marginBottom: "0.15rem" }}>
              Live Stream
            </h1>
            <p style={{ fontSize: "14px", color: "var(--wiki-ink-faint)" }}>
              What Jaromelu is watching, thinking, and doing — right now.
            </p>
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4 justify-center" style={{ borderBottom: "1px solid var(--wiki-border)", paddingBottom: "0.75rem" }}>
          <div className="flex gap-1">
            {(Object.keys(FILTER_TYPES) as FilterKey[]).map((key) => (
              <button
                key={key}
                onClick={() => setFilter(key)}
                className="px-3 py-1.5 text-xs font-semibold rounded-md transition-colors"
                style={{
                  letterSpacing: "0.06em",
                  textTransform: "uppercase",
                  backgroundColor: filter === key ? "var(--wiki-accent-bg)" : "transparent",
                  color: filter === key ? "var(--wiki-accent)" : "var(--wiki-ink-faint)",
                }}
              >
                {key}
              </button>
            ))}
          </div>
          <span style={{ fontSize: "12px", color: "var(--wiki-ink-faint)", marginLeft: "auto" }}>
            {filtered.length} entries
          </span>
        </div>

        {/* Icon key */}
        <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 justify-center">
          {ICON_KEY.map(({ icon: Icon, label, color }) => (
            <span key={label} className="flex items-center gap-1.5">
              <Icon size={11} style={{ color }} />
              <span style={{ fontSize: "10px", color: "var(--wiki-ink-faint)" }}>{label}</span>
            </span>
          ))}
        </div>

        {/* Stream — scrollable */}
        <div ref={scrollRef} className="light-scrollbar flex-1 overflow-y-auto pb-4">
          {filtered.length === 0 && !loading ? (
            <div className="py-20 text-center" style={{ fontSize: "14px", color: "var(--wiki-ink-faint)" }}>
              Waiting for input...
            </div>
          ) : (
            <div>
              {filtered.length > 0 && (
                <div className="pb-2 text-center" style={{ fontSize: "11px", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--wiki-ink-faint)" }}>
                  Beginning of stream
                </div>
              )}

              {itemsWithDividers.map((entry, i) =>
                entry.type === "divider" ? (
                  <DayDivider key={`div-${entry.label}`} label={entry.label} />
                ) : (
                  <FeedItemCard key={entry.item.id} item={entry.item} />
                )
              )}

              {/* Thinking indicator */}
              {loading && (
                <div className="flex gap-0 py-2.5">
                  <div className="w-12 shrink-0" />
                  <div className="w-8 shrink-0 flex items-start justify-center" style={{ paddingTop: "0.25rem" }}>
                    <BotMessageSquare size={14} style={{ color: "var(--wiki-accent)" }} />
                  </div>
                  <span className="animate-pulse" style={{ fontSize: "14px", fontStyle: "italic", color: "var(--wiki-ink-faint)" }}>thinking...</span>
                </div>
              )}

              {error && !loading && (
                <div className="flex gap-0 py-2.5">
                  <div className="w-12 shrink-0" />
                  <div className="w-8 shrink-0" />
                  <span style={{ fontSize: "14px", color: "var(--red, #9a2020)" }}>{error}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Chat input */}
        <div className="pb-4 pt-3">
          <ChatInputBar
            value={input}
            onChange={setInput}
            onSubmit={submit}
            temperature={temperature}
            onTemperatureChange={setTemperature}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}
