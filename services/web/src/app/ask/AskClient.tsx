"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { SendHorizonal } from "lucide-react";
import { apiPost } from "@/lib/api";
import type { ChatMessage, TemperatureMode, AskRequest, AskResponse } from "./ask-data";

const SUGGESTED_PROMPTS = [
  "Should I trade Cleary this week?",
  "Who's the best captain for this round?",
  "Which mid-range forwards are worth targeting?",
  "Why did you sell Munster?",
];

const TEMP_LABELS: { key: TemperatureMode; label: string }[] = [
  { key: "straight", label: "Straight" },
  { key: "sharp", label: "Sharp" },
  { key: "roast", label: "Roast" },
];

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

export default function AskClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [temperature, setTemperature] = useState<TemperatureMode>("sharp");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const submit = useCallback(
    async (question: string) => {
      if (!question.trim() || loading) return;

      setError(null);
      const userMsg: ChatMessage = { id: nextId(), role: "user", text: question.trim() };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);

      try {
        const res = await apiPost<AskResponse, AskRequest>("/api/ask", {
          question: question.trim(),
          temperature,
        });

        const jeromMsg: ChatMessage = {
          id: nextId(),
          role: "jeromelu",
          text: res.answer,
          sources: res.sources.map((s) => ({
            sourceId: s.source_id,
            title: s.title,
            creator: s.creator_name ?? undefined,
          })),
          players: res.players.map((p) => ({
            entityId: p.entity_id,
            name: p.name,
          })),
        };
        setMessages((prev) => [...prev, jeromMsg]);
      } catch {
        setError("Something broke. Even I have bad days. Try again.");
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

  const isEmpty = messages.length === 0 && !loading;

  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-3xl flex-col px-4 pt-14">
      {/* Messages area */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto pb-4">
        {isEmpty ? (
          <EmptyState onSelect={submit} />
        ) : (
          <div className="space-y-4 py-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            {loading && <TypingIndicator />}
            {error && !loading && (
              <div className="border-l-2 border-red-500/50 pl-3 text-sm text-red-400">
                {error}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Input area */}
      <div className="border-t border-zinc-800/30 pb-4 pt-3">
        {/* Temperature toggle */}
        <div className="mb-2 flex items-center gap-1">
          <span className="mr-2 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
            tone
          </span>
          {TEMP_LABELS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setTemperature(key)}
              className="rounded px-2 py-0.5 font-mono text-[11px] transition-colors"
              style={{
                color: temperature === key ? "var(--tigers-orange)" : "rgb(82, 82, 91)",
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

function EmptyState({ onSelect }: { onSelect: (q: string) => void }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6">
      <div className="text-center">
        <p className="font-mono text-xs text-zinc-600">&gt; ask me anything</p>
      </div>
      <div className="grid w-full max-w-md grid-cols-1 gap-2 sm:grid-cols-2">
        {SUGGESTED_PROMPTS.map((prompt) => (
          <button
            key={prompt}
            onClick={() => onSelect(prompt)}
            className="rounded border border-zinc-800/50 px-3 py-2.5 text-left text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-200"
          >
            {prompt}
          </button>
        ))}
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] ${
          isUser
            ? "rounded-lg bg-zinc-800/60 px-3 py-2"
            : "border-l-2 pl-3"
        }`}
        style={!isUser ? { borderColor: "var(--tigers-orange)" } : undefined}
      >
        {!isUser && (
          <span className="mb-1 block font-mono text-[10px] uppercase tracking-wider text-zinc-600">
            jeromelu
          </span>
        )}
        <p className="whitespace-pre-wrap text-sm text-zinc-200">{message.text}</p>

        {/* Source references */}
        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.sources.map((s) => (
              <span
                key={s.sourceId}
                className="font-mono text-[10px] text-zinc-500"
              >
                via {s.creator || s.title}
              </span>
            ))}
          </div>
        )}

        {/* Player references */}
        {message.players && message.players.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.players.map((p) => (
              <span
                key={p.entityId}
                className="rounded bg-zinc-800/50 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400 transition-colors hover:text-[var(--tigers-orange)]"
              >
                {p.name}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function TypingIndicator() {
  return (
    <div className="flex justify-start">
      <div className="border-l-2 pl-3" style={{ borderColor: "var(--tigers-orange)" }}>
        <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-600">
          jeromelu
        </span>
        <p className="animate-pulse text-sm text-zinc-500">thinking...</p>
      </div>
    </div>
  );
}
