"use client";

import { useState, useCallback, useRef, useEffect, useMemo } from "react";
import { apiPost } from "@/lib/api";
import ChatInputBar from "@/app/components/ChatInputBar";
import type { TemperatureMode } from "@/app/components/ChatInputBar";
import type {
  ChatMessage,
  AskRequest,
  AskResponse,
} from "./ask-data";

/* ── Category pills (Jaromelu's voice) ── */
const CATEGORIES = [
  { label: "SuperCoach", prompt: "What moves should I be making in SuperCoach this week?" },
  { label: "This round", prompt: "Break down the key match-ups this round." },
  { label: "Player intel", prompt: "Who should I be watching right now and why?" },
  { label: "What's the goss?", prompt: "What's the latest NRL news and goss?" },
  { label: "Roast me", prompt: "Roast my squad decisions this season." },
];


/* ── Greeting + subline ── */
function getGreeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Up late, Coach?";
  if (h < 12) return "Morning, Coach";
  if (h < 17) return "What's good, Coach";
  return "Evening, Coach";
}

const SUBLINES = [
  "I've been watching the tape.",
  "Got some thoughts on your halves.",
  "Round's coming up fast.",
  "I've got opinions. You ready?",
  "Been crunching the numbers.",
  "Ask me anything. I dare you.",
  "I know things.",
  "Let's talk footy.",
];

function getSubline(): string {
  return SUBLINES[Math.floor(Math.random() * SUBLINES.length)];
}

let msgCounter = 0;
function nextId() {
  return `msg-${++msgCounter}-${Date.now()}`;
}

/* ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */

export default function AskClient() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [temperature, setTemperature] = useState<TemperatureMode>("sharp");
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const greeting = useMemo(() => getGreeting(), []);
  const subline = useMemo(() => getSubline(), []);
  const isEmpty = messages.length === 0 && !loading;

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const submit = useCallback(
    async (question: string) => {
      if (!question.trim() || loading) return;

      setError(null);
      const userMsg: ChatMessage = {
        id: nextId(),
        role: "user",
        text: question.trim(),
      };
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
          role: "jaromelu",
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
      }
    },
    [loading, temperature],
  );

  /* ── Input bar (shared between empty + chat states) ── */
  const inputBar = (
    <ChatInputBar
      value={input}
      onChange={setInput}
      onSubmit={submit}
      temperature={temperature}
      onTemperatureChange={setTemperature}
      loading={loading}
      placeholder="Go on, ask me anything..."
    />
  );

  /* ━━ Empty state ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  if (isEmpty) {
    return (
      <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-5xl flex-col px-6">
        {/* Greeting — centered in the available space above the input */}
        <div className="flex flex-1 flex-col items-center justify-center">
          <h1
            className="mb-2 text-center text-4xl font-light tracking-tight sm:text-5xl"
            style={{
              fontFamily: "var(--font-serif), Georgia, serif",
              color: "var(--foreground)",
            }}
          >
            {greeting}
          </h1>
          <p
            className="text-center text-sm italic"
            style={{ color: "var(--foreground-muted)" }}
          >
            {subline}
          </p>

          {/* Category pills */}
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            {CATEGORIES.map(({ label, prompt }) => (
              <button
                key={label}
                onClick={() => submit(prompt)}
                className="rounded-full border px-4 py-1.5 text-xs transition-colors"
                style={{
                  borderColor: "var(--border)",
                  color: "var(--foreground-muted)",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.borderColor = "var(--accent-border)";
                  e.currentTarget.style.color = "var(--foreground)";
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "var(--border)";
                  e.currentTarget.style.color = "var(--foreground-muted)";
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Input pinned to bottom — same position as feed */}
        <div className="pb-4 pt-3">{inputBar}</div>
      </div>
    );
  }

  /* ━━ Chat state ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ */
  return (
    <div className="mx-auto flex h-[calc(100vh-3.5rem)] max-w-5xl flex-col px-6 pt-14">
      {/* Messages */}
      <div ref={scrollRef} className="custom-scrollbar flex-1 overflow-y-auto pb-4">
        <div className="space-y-4 py-4">
          {messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))}
          {loading && <TypingIndicator />}
          {error && !loading && (
            <div
              className="border-l-2 pl-3 text-sm"
              style={{
                borderColor: "var(--red)",
                color: "var(--red)",
              }}
            >
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Bottom input */}
      <div className="pb-4 pt-3">{inputBar}</div>
    </div>
  );
}

/* ── Sub-components ── */

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] ${
          isUser ? "rounded-lg px-3 py-2" : "border-l-2 pl-3"
        }`}
        style={
          isUser
            ? { backgroundColor: "var(--surface)" }
            : { borderColor: "var(--accent)" }
        }
      >
        {!isUser && (
          <span
            className="mb-1 block font-mono text-[10px] uppercase tracking-wider"
            style={{ color: "var(--foreground-ghost)" }}
          >
            jaromelu
          </span>
        )}
        <p
          className="whitespace-pre-wrap text-sm"
          style={{ color: "var(--foreground)" }}
        >
          {message.text}
        </p>

        {message.sources && message.sources.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {message.sources.map((s) => (
              <span
                key={s.sourceId}
                className="font-mono text-[10px]"
                style={{ color: "var(--foreground-ghost)" }}
              >
                via {s.creator || s.title}
              </span>
            ))}
          </div>
        )}

        {message.players && message.players.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {message.players.map((p) => (
              <span
                key={p.entityId}
                className="rounded px-1.5 py-0.5 font-mono text-[10px] transition-colors"
                style={{
                  backgroundColor: "var(--border)",
                  color: "var(--foreground-secondary)",
                }}
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
      <div
        className="border-l-2 pl-3"
        style={{ borderColor: "var(--accent)" }}
      >
        <span
          className="font-mono text-[10px] uppercase tracking-wider"
          style={{ color: "var(--foreground-ghost)" }}
        >
          jaromelu
        </span>
        <p
          className="animate-pulse text-sm"
          style={{ color: "var(--foreground-ghost)" }}
        >
          thinking...
        </p>
      </div>
    </div>
  );
}
