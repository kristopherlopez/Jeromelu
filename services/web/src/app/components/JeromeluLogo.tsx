"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  MessageCircle,
  Zap,
  ClipboardList,
  Brain,
  TrendingUp,
  Trophy,
  User,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useNavHover } from "./NavHoverContext";

export interface LetterConfig {
  char: string;
  key: string;
  label: string;
  href: string;
  delay: number; // ms delay for entrance animation
  icon: LucideIcon;
}

export const LETTERS: LetterConfig[] = [
  { char: "J", key: "j", label: "Chat", href: "/", delay: 0, icon: MessageCircle },
  { char: "e", key: "e", label: "Energy", href: "/energy", delay: 700, icon: Zap },
  { char: "r", key: "r", label: "Roster", href: "/roster", delay: 500, icon: ClipboardList },
  { char: "o", key: "o", label: "On my mind", href: "/stream", delay: 400, icon: Brain },
  { char: "m", key: "m", label: "Market", href: "/market", delay: 300, icon: TrendingUp },
  { char: "e", key: "e", label: "Energy", href: "/energy", delay: 200, icon: Zap },
  { char: "l", key: "l", label: "Leaderboard", href: "/leaderboard", delay: 100, icon: Trophy },
  { char: "u", key: "u", label: "You", href: "/settings", delay: 0, icon: User },
];

const DEFAULT_TAGLINE =
  "AI-powered NRL SuperCoach analyst. Watching everything. Reading everyone. Making moves.";

// Outside-in for both phases: J, u, e(1), l, r, e(2), o, m
const OUTSIDE_IN = [0, 7, 1, 6, 2, 5, 3, 4];
const STAGGER_MS = 80;

export default function JeromeluLogo() {
  const router = useRouter();
  const [litLetters, setLitLetters] = useState<Set<number>>(new Set());
  const [animationDone, setAnimationDone] = useState(false);
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { hoveredHref, setHoveredHref } = useNavHover();

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

    // Mark animation complete
    const doneAt = allLitAt + pauseAfterLit + OUTSIDE_IN.length * STAGGER_MS + 200;
    const done = setTimeout(() => {
      setAnimationDone(true);
    }, doneAt);
    timeouts.push(done);

    return () => timeouts.forEach(clearTimeout);
  }, []);

  // Keyboard shortcuts
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't trigger if user is typing in an input
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      const letter = LETTERS.find((l) => l.key === e.key.toLowerCase());
      if (letter) {
        router.push(letter.href);
      }
    },
    [router]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Effective hovered index: local hover takes priority, then corner nav hover
  const effectiveIndex = hoveredIndex ?? (
    hoveredHref !== null
      ? LETTERS.findIndex((l) => l.href === hoveredHref)
      : null
  );

  // Determine if a letter is "lit" (orange) — entrance animation OR hover
  const getIsLit = (index: number): boolean => {
    if (litLetters.has(index)) return true;
    if (effectiveIndex === null) return false;

    // If hovering an "e", light both "e"s
    if (LETTERS[effectiveIndex].char === "e" && LETTERS[index].char === "e") {
      return true;
    }
    // Match by href for corner nav (lights up all letters sharing that route)
    if (hoveredIndex === null && hoveredHref !== null) {
      return LETTERS[index].href === hoveredHref;
    }
    return effectiveIndex === index;
  };

  // Check if a letter should be dimmed (another letter is hovered, but not this one)
  const getIsDimmed = (index: number): boolean => {
    if (!animationDone || effectiveIndex === null) return false;
    // If hovering an "e", don't dim either "e"
    if (LETTERS[effectiveIndex].char === "e" && LETTERS[index].char === "e") {
      return false;
    }
    if (hoveredIndex === null && hoveredHref !== null) {
      return LETTERS[index].href !== hoveredHref;
    }
    return effectiveIndex !== index;
  };

  const handleClick = (letter: LetterConfig) => {
    router.push(letter.href);
  };

  const handleMouseEnter = (index: number) => {
    setHoveredIndex(index);
    setHoveredHref(LETTERS[index].href);
  };

  const handleMouseLeave = () => {
    setHoveredIndex(null);
    setHoveredHref(null);
  };

  // Build the hover tagline
  const hoveredLetter = effectiveIndex !== null ? LETTERS[effectiveIndex] : null;
  const HoveredIcon = hoveredLetter?.icon ?? null;

  return (
    <div className="flex flex-col items-center gap-6">
      {/* Letters */}
      <div className="relative flex items-center gap-0">
        {LETTERS.map((letter, i) => {
          const isLit = getIsLit(i);
          const isDimmed = getIsDimmed(i);

          return (
            <button
              key={i}
              onClick={() => handleClick(letter)}
              onMouseEnter={() => handleMouseEnter(i)}
              onMouseLeave={handleMouseLeave}
              className="relative px-[2px] text-6xl font-bold tracking-tight transition-all duration-300 cursor-pointer select-none focus:outline-none"
              style={{
                color: isLit ? "var(--tigers-orange)" : "var(--foreground)",
                textShadow: isLit
                  ? "0 0 20px var(--tigers-orange-glow), 0 0 40px var(--tigers-orange-glow)"
                  : "none",
                opacity: isDimmed ? 0.4 : 1,
                transform: isLit && animationDone && effectiveIndex !== null ? "scale(1.1)" : "scale(1)",
              }}
              aria-label={`${letter.label} (press ${letter.key})`}
            >
              {letter.char}
            </button>
          );
        })}
      </div>

      {/* Tagline with crossfade */}
      <div className="grid w-full max-w-md [&>*]:col-start-1 [&>*]:row-start-1">
        <p
          className="text-center text-lg leading-7 text-zinc-400 transition-opacity duration-300"
          style={{ opacity: hoveredLetter ? 0 : 1 }}
        >
          {DEFAULT_TAGLINE}
        </p>
        <p
          className="flex items-center justify-center gap-2 text-lg leading-7 transition-opacity duration-300"
          style={{
            opacity: hoveredLetter ? 1 : 0,
            color: "var(--tigers-orange)",
          }}
        >
          {HoveredIcon && <HoveredIcon size={18} className="shrink-0" style={{ position: "relative", top: "1px" }} />}
          <span>{hoveredLetter ? `[${hoveredLetter.key}] ${hoveredLetter.label}` : "\u00A0"}</span>
        </p>
      </div>
    </div>
  );
}
