"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Users,
  FileText,
  BookOpen,
  MessageCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// LETTERS config is still exported for the Sidebar to use
export interface LetterConfig {
  char: string;
  key: string;
  label: string;
  href: string;
  delay: number;
  icon: LucideIcon;
}

export const LETTERS: LetterConfig[] = [
  { char: "J", key: "j", label: "The Feed", href: "/feed", delay: 0, icon: Activity },
  { char: "e", key: "e", label: "The Feed", href: "/feed", delay: 700, icon: Activity },
  { char: "r", key: "r", label: "My Squad", href: "/squad", delay: 500, icon: Users },
  { char: "o", key: "o", label: "The Dossier", href: "/dossier", delay: 400, icon: FileText },
  { char: "m", key: "m", label: "The Ledger", href: "/ledger", delay: 300, icon: BookOpen },
  { char: "e", key: "e", label: "The Feed", href: "/feed", delay: 200, icon: Activity },
  { char: "l", key: "l", label: "The Ledger", href: "/ledger", delay: 100, icon: BookOpen },
  { char: "u", key: "u", label: "Ask Me", href: "/ask", delay: 0, icon: MessageCircle },
];

const DEFAULT_TAGLINE =
  "I watch everything. I read everyone. I make moves.";

// Outside-in for both phases: J, u, e(1), l, r, e(2), o, m
const OUTSIDE_IN = [0, 7, 1, 6, 2, 5, 3, 4];
const STAGGER_MS = 80;

export default function JeromeluLogo() {
  const [litLetters, setLitLetters] = useState<Set<number>>(new Set());

  // Entrance animation — orange sweeps in from ends, then white sweeps in from ends
  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];

    // Phase 1: Orange from both ends to middle
    OUTSIDE_IN.forEach((letterIndex, step) => {
      const t = setTimeout(() => {
        setLitLetters((prev) => {
          const next = new Set(prev);
          next.add(letterIndex);
          return next;
        });
      }, step * STAGGER_MS);
      timeouts.push(t);
    });

    const allLitAt = OUTSIDE_IN.length * STAGGER_MS;
    const pauseAfterLit = 300;

    // Phase 2: White from both ends to middle (same outside-in order)
    OUTSIDE_IN.forEach((letterIndex, step) => {
      const t = setTimeout(() => {
        setLitLetters((prev) => {
          const next = new Set(prev);
          next.delete(letterIndex);
          return next;
        });
      }, allLitAt + pauseAfterLit + step * STAGGER_MS);
      timeouts.push(t);
    });

    return () => timeouts.forEach(clearTimeout);
  }, []);

  return (
    <div className="flex flex-col items-center gap-4">
      {/* Letters — display only, entrance animation */}
      <div className="relative flex items-center gap-0">
        {LETTERS.map((letter, i) => {
          const isLit = litLetters.has(i);

          return (
            <span
              key={i}
              className="relative px-[2px] text-6xl font-bold tracking-tight transition-all duration-300 select-none"
              style={{
                color: isLit ? "var(--tigers-orange)" : "var(--foreground)",
                textShadow: isLit
                  ? "0 0 20px var(--tigers-orange-glow), 0 0 40px var(--tigers-orange-glow)"
                  : "none",
              }}
            >
              {letter.char}
            </span>
          );
        })}
      </div>

      {/* Tagline */}
      <p className="text-center text-lg leading-7 text-zinc-400">
        {DEFAULT_TAGLINE}
      </p>
    </div>
  );
}
