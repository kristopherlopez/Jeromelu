"use client";

import { useRef, useState } from "react";
import { SendHorizonal } from "lucide-react";
import { useTheme } from "./ThemeContext";

export type TemperatureMode = "straight" | "sharp" | "roast";

const TEMP_LABELS: { key: TemperatureMode; label: string }[] = [
  { key: "straight", label: "Straight" },
  { key: "sharp", label: "Sharp" },
  { key: "roast", label: "Roast" },
];

/** Token sets for light (wiki/parchment) vs dark themes */
const TOKENS = {
  light: {
    border: "var(--wiki-border, rgba(28,26,20,0.12))",
    surface: "var(--wiki-surface, #FFFFFF)",
    accent: "var(--wiki-accent, #b85c38)",
    accentBg: "var(--wiki-accent-bg, #FFF0E8)",
    foreground: "var(--wiki-ink, #1c1a14)",
    muted: "var(--wiki-ink-faint, #9c9484)",
  },
  dark: {
    border: "var(--border)",
    surface: "var(--surface)",
    accent: "var(--accent)",
    accentBg: "var(--accent-bg)",
    foreground: "var(--foreground)",
    muted: "var(--foreground-ghost)",
  },
} as const;

interface ChatInputBarProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: (value: string) => void;
  temperature: TemperatureMode;
  onTemperatureChange: (mode: TemperatureMode) => void;
  loading?: boolean;
  placeholder?: string;
}

export default function ChatInputBar({
  value,
  onChange,
  onSubmit,
  temperature,
  onTemperatureChange,
  loading = false,
  placeholder = "Ask me anything about SuperCoach...",
}: ChatInputBarProps) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const [hoveredTemp, setHoveredTemp] = useState<TemperatureMode | null>(null);
  const { isLight } = useTheme();
  const t = isLight ? TOKENS.light : TOKENS.dark;

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSubmit(value);
    }
  };

  return (
    <div
      className="w-full rounded-xl border p-3 transition-colors"
      style={{
        borderColor: t.border,
        backgroundColor: t.surface,
      }}
    >
      {/* Temperature toggle */}
      <div className="mb-2 flex items-center gap-1">
        <span
          className="mr-2 font-mono text-[10px] uppercase tracking-wider"
          style={{ color: t.muted }}
        >
          tone
        </span>
        {TEMP_LABELS.map(({ key, label }) => {
          const isActive = temperature === key;
          const isHovered = hoveredTemp === key;

          return (
            <button
              key={key}
              onClick={() => onTemperatureChange(key)}
              onMouseEnter={() => setHoveredTemp(key)}
              onMouseLeave={() => setHoveredTemp(null)}
              className="rounded px-2 py-0.5 font-mono text-[11px]"
              style={{
                color: isActive
                  ? t.accent
                  : isHovered
                    ? t.foreground
                    : t.muted,
                backgroundColor: isActive || isHovered
                  ? t.accentBg
                  : "transparent",
                transform: isHovered && !isActive ? "translateY(-1px)" : "none",
                transition: "color 200ms, background-color 200ms, transform 200ms",
              }}
            >
              {label}
            </button>
          );
        })}
      </div>

      {/* Input row */}
      <div className="flex items-end gap-2">
        <textarea
          ref={inputRef}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          rows={1}
          disabled={loading}
          className="flex-1 resize-none bg-transparent text-sm outline-none disabled:opacity-50"
          style={{
            color: t.foreground,
            minHeight: "1.75rem",
            maxHeight: "8rem",
          }}
        />
        <button
          onClick={() => onSubmit(value)}
          disabled={!value.trim() || loading}
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg disabled:opacity-30"
          style={{
            color: value.trim() ? t.accent : t.muted,
            backgroundColor: value.trim() ? t.accentBg : "transparent",
            transition: "color 200ms, background-color 200ms",
          }}
        >
          <SendHorizonal size={16} />
        </button>
      </div>
    </div>
  );
}
