"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  BookOpen,
  FileText,
  MessageCircle,
  Moon,
  Newspaper,
  Radio,
  Sun,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import { useTheme } from "./ThemeContext";
import { useTeam } from "./TeamContext";
import { TEAMS } from "./teams";
import { LETTERS } from "./JeromeluLogo";
import type { FeedResponse } from "../feed/feed-data";
import type { WikiChangeItem } from "../wiki/wiki-data";

export const TOPBAR_HEIGHT = 56;

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV_ITEMS: NavItem[] = [
  { label: "The Feed", href: "/", icon: Activity },
  { label: "The Wiki", href: "/wiki", icon: FileText },
  { label: "The Ledger", href: "/ledger", icon: BookOpen },
  { label: "The Analysis", href: "/insights", icon: Newspaper },
  { label: "Ask Me", href: "/ask", icon: MessageCircle },
  { label: "Live Pulse", href: "/pulse", icon: Radio },
];

const ACTIVITY_COLORS: Record<string, string> = {
  watching: "var(--foreground-muted, #948878)",
  signal: "var(--accent, #d4874a)",
  thinking: "var(--lilac, #a898c8)",
  prediction: "var(--teal, #5a9e8a)",
  action: "var(--accent, #d4874a)",
  review: "var(--ochre, #c4a840)",
  sys: "var(--foreground-muted, #948878)",
  wiki: "var(--terracotta, #b85c38)",
};

const ACTIVITY_LABELS: Record<string, string> = {
  watching: "watching",
  signal: "spotted signal",
  thinking: "thinking",
  prediction: "made prediction",
  action: "took action",
  review: "reviewing",
  sys: "system",
  wiki: "updated wiki",
};

const ACTIVITY_TYPES = new Set([
  "watching",
  "signal",
  "thinking",
  "prediction",
  "action",
  "review",
  "sys",
]);

type ActivityItem = {
  key: string;
  label: string;
  sub: string;
  activityType: string;
  href?: string;
  ts: string;
};

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "now";
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h`;
  const days = Math.floor(hrs / 24);
  return `${days}d`;
}

const OUTSIDE_IN = [0, 7, 1, 6, 2, 5, 3, 4];
const AVATAR_SIZE = 32;

export function JeromeluTopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { mode, setMode, isLight } = useTheme();
  const { slug: teamSlug, team, setTeam } = useTeam();
  const { triggerClip } = useAvatarEngine();

  const isHome = pathname === "/landing";
  const isAdmin = pathname.startsWith("/admin");
  const isStream = pathname.startsWith("/wiki/source");

  // Hooks must run unconditionally — early-return only after all hooks declared.
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [activityOpen, setActivityOpen] = useState(false);
  const [teamPickerOpen, setTeamPickerOpen] = useState(false);
  const [ringPulseColor, setRingPulseColor] = useState<string | null>(null);
  const [hoveredHref, setHoveredHref] = useState<string | null>(null);
  const [litLetters, setLitLetters] = useState<Set<number>>(new Set());
  const sweepTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const teamPickerRef = useRef<HTMLDivElement | null>(null);

  // Activity feed — same data source as the old sidebar
  useEffect(() => {
    if (isHome || isAdmin || isStream) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL!;
    Promise.allSettled([
      fetch(`${apiBase}/api/feed?limit=20`).then((r) => r.json()) as Promise<FeedResponse>,
      fetch(`${apiBase}/api/wiki/recent-changes?limit=10`).then((r) => r.json()) as Promise<{
        items: WikiChangeItem[];
      }>,
    ]).then(([feedResult, wikiResult]) => {
      const items: ActivityItem[] = [];
      if (feedResult.status === "fulfilled") {
        for (const fi of feedResult.value.items) {
          if (!ACTIVITY_TYPES.has(fi.type)) continue;
          items.push({
            key: `feed-${fi.id}`,
            label: fi.text.slice(0, 60) + (fi.text.length > 60 ? "..." : ""),
            sub: fi.type,
            activityType: fi.type,
            ts: fi.timestamp,
          });
        }
      }
      if (wikiResult.status === "fulfilled") {
        for (const wc of wikiResult.value.items || []) {
          const href =
            wc.page_type === "round"
              ? `/wiki/round/${wc.page_slug.replace(/^round-(\d+)-(\d+)$/, "$1/$2")}`
              : `/wiki/${wc.page_type}/${wc.page_slug}`;
          items.push({
            key: `wiki-${wc.revision_id}`,
            label: wc.page_title,
            sub: wc.summary || "wiki update",
            activityType: "wiki",
            href,
            ts: wc.created_at,
          });
        }
      }
      items.sort((a, b) => (b.ts || "").localeCompare(a.ts || ""));
      const top = items.slice(0, 15);
      setRecentActivity(top);
      if (top.length > 0) {
        const color = ACTIVITY_COLORS[top[0].activityType] || ACTIVITY_COLORS.watching;
        setRingPulseColor(color);
        const t = setTimeout(() => setRingPulseColor(null), 2000);
        return () => clearTimeout(t);
      }
    });
  }, [isHome, isAdmin, isStream, pathname]);

  // Click-outside to close the activity dropdown
  useEffect(() => {
    if (!activityOpen) return;
    const onClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setActivityOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [activityOpen]);

  // Click-outside to close the team picker
  useEffect(() => {
    if (!teamPickerOpen) return;
    const onClick = (e: MouseEvent) => {
      if (teamPickerRef.current && !teamPickerRef.current.contains(e.target as Node)) {
        setTeamPickerOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [teamPickerOpen]);

  const runLogoSweep = useCallback(() => {
    sweepTimersRef.current.forEach(clearTimeout);
    sweepTimersRef.current = [];
    setLitLetters(new Set());
    const STAGGER = 80;
    const allLitAt = OUTSIDE_IN.length * STAGGER;
    const pause = 300;
    OUTSIDE_IN.forEach((letterIndex, step) => {
      sweepTimersRef.current.push(
        setTimeout(() => setLitLetters((prev) => new Set(prev).add(letterIndex)), step * STAGGER),
      );
    });
    OUTSIDE_IN.forEach((letterIndex, step) => {
      sweepTimersRef.current.push(
        setTimeout(() => {
          setLitLetters((prev) => {
            const n = new Set(prev);
            n.delete(letterIndex);
            return n;
          });
        }, allLitAt + pause + step * STAGGER),
      );
    });
  }, []);

  const status = useMemo(() => {
    if (recentActivity.length === 0) {
      return { color: "var(--tigers-orange, #d4874a)", text: "online" };
    }
    const top = recentActivity[0];
    return {
      color: ACTIVITY_COLORS[top.activityType] || ACTIVITY_COLORS.watching,
      text: `${ACTIVITY_LABELS[top.activityType] || top.activityType} · ${relativeTime(top.ts)}`,
    };
  }, [recentActivity]);

  // Now safe to early-return
  if (isHome || isAdmin || isStream) return null;

  // ── Theme tokens ──
  // Accent tokens always read from CSS vars — ThemeApplier writes the
  // current team's accent to `--accent` etc. for both light and dark modes.
  const bg = isLight ? "var(--wiki-surface, #ffffff)" : "var(--background-deep, #241e1a)";
  const border = isLight ? "var(--wiki-border, rgba(28,26,20,0.08))" : "var(--border, #3e3630)";
  const accent = "var(--accent)";
  const accentBg = "var(--accent-bg)";
  const accentBorder = "var(--accent-border)";
  const labelMuted = isLight ? "rgba(92,64,48,0.55)" : "var(--foreground-muted, #948878)";
  const labelHover = isLight ? "#5c4030" : "var(--foreground-secondary, #c0b4a0)";
  const labelDim = isLight ? "rgba(92,64,48,0.35)" : "var(--foreground-muted, #948878)";

  return (
    <header
      className="fixed top-0 left-0 right-0 z-50 flex items-center"
      style={{
        height: TOPBAR_HEIGHT,
        backgroundColor: bg,
        borderBottom: `1px solid ${border}`,
        paddingLeft: 20,
        paddingRight: 20,
      }}
    >
      {/* ── Left: Jaromelu wordmark ── */}
      <button
        className="flex items-center gap-0 cursor-pointer select-none focus:outline-none shrink-0"
        onClick={() => router.push("/landing")}
        onMouseEnter={runLogoSweep}
        aria-label="Home"
      >
        {LETTERS.map((letter, i) => {
          const isLit = litLetters.has(i);
          return (
            <span
              key={i}
              className="text-xl font-bold tracking-tight"
              style={{
                fontFamily: "Georgia, serif",
                padding: "0 0.5px",
                color: isLit ? accent : labelDim,
                textShadow: isLit
                  ? isLight
                    ? "0 0 8px rgba(184,92,56,0.3)"
                    : "0 0 10px var(--accent-glow), 0 0 20px var(--accent-glow)"
                  : "none",
                transition: "color 200ms, text-shadow 200ms",
              }}
            >
              {letter.char}
            </span>
          );
        })}
      </button>

      {/* ── Center: Pill nav ── */}
      <nav className="flex-1 flex items-center justify-center gap-1 min-w-0 px-4">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          const isHovered = hoveredHref === item.href;
          const Icon = item.icon;
          const tinted = isActive || isHovered;
          return (
            <button
              key={item.href}
              className="flex items-center gap-2 rounded-full cursor-pointer focus:outline-none whitespace-nowrap"
              style={{
                padding: "6px 14px",
                backgroundColor: tinted ? accentBg : "transparent",
                border: `1px solid ${tinted ? accentBorder : "transparent"}`,
                transition: "background-color 180ms, border-color 180ms, color 180ms",
              }}
              onClick={() => {
                triggerClip("directional", "glance-down");
                router.push(item.href);
              }}
              onMouseEnter={() => setHoveredHref(item.href)}
              onMouseLeave={() => setHoveredHref(null)}
            >
              <Icon
                size={14}
                style={{
                  color: tinted ? accent : labelMuted,
                  transition: "color 180ms",
                }}
              />
              <span
                className="text-[13px] font-medium"
                style={{
                  fontFamily: "Georgia, serif",
                  letterSpacing: "0.01em",
                  color: isActive ? accent : isHovered ? labelHover : labelMuted,
                  transition: "color 180ms",
                }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* ── Right: avatar + status + theme switcher ── */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Avatar with ring pulse */}
        <div
          className="rounded-full relative"
          style={{
            transition: "box-shadow 600ms ease",
            boxShadow: ringPulseColor
              ? `0 0 12px 3px ${ringPulseColor}, 0 0 20px 6px color-mix(in srgb, ${ringPulseColor} 30%, transparent)`
              : "none",
          }}
        >
          <ConnectedAvatar size={AVATAR_SIZE} light={isLight} />
        </div>

        {/* Status + activity dropdown */}
        <div className="relative" ref={dropdownRef}>
          <button
            className="flex items-center gap-1.5 text-[12px] cursor-pointer focus:outline-none"
            style={{
              fontFamily: "Georgia, serif",
              fontStyle: "italic",
              background: "none",
              border: "none",
              padding: "4px 6px",
              color: labelMuted,
            }}
            onClick={() => setActivityOpen((v) => !v)}
            title={activityOpen ? "Hide activity" : "Show recent activity"}
          >
            <span className="relative flex h-1.5 w-1.5 shrink-0">
              <span
                className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
                style={{ backgroundColor: status.color }}
              />
              <span
                className="relative inline-flex h-1.5 w-1.5 rounded-full"
                style={{ backgroundColor: status.color }}
              />
            </span>
            <span className="whitespace-nowrap">{status.text}</span>
            <span
              style={{
                fontSize: "8px",
                transform: activityOpen ? "rotate(180deg)" : "rotate(0deg)",
                transition: "transform 200ms",
                marginLeft: 2,
              }}
            >
              ▾
            </span>
          </button>

          {/* Dropdown panel */}
          {activityOpen && recentActivity.length > 0 && (
            <div
              className="absolute right-0 light-scrollbar"
              style={{
                top: "calc(100% + 8px)",
                width: 320,
                maxHeight: 360,
                overflowY: "auto",
                backgroundColor: bg,
                border: `1px solid ${border}`,
                borderRadius: 8,
                boxShadow: isLight
                  ? "0 8px 24px rgba(28,26,20,0.10)"
                  : "0 8px 24px rgba(0,0,0,0.35)",
                padding: "10px 14px 12px",
              }}
            >
              <div className="relative" style={{ paddingLeft: 14 }}>
                <div
                  className="absolute"
                  style={{
                    left: 5,
                    top: 10,
                    bottom: 10,
                    width: 1.5,
                    background: isLight
                      ? "linear-gradient(to bottom, rgba(120,60,30,0.25), rgba(120,60,30,0.05))"
                      : "linear-gradient(to bottom, var(--border-subtle), transparent)",
                    borderRadius: 1,
                  }}
                />
                {recentActivity.map((item, i) => {
                  const color = ACTIVITY_COLORS[item.activityType] || ACTIVITY_COLORS.watching;
                  const isFirst = i === 0;
                  const content = (
                    <div className="flex items-start gap-2.5 py-1.5">
                      <span
                        className="shrink-0 rounded-full relative"
                        style={{
                          width: isFirst ? 9 : 7,
                          height: isFirst ? 9 : 7,
                          backgroundColor: color,
                          marginLeft: isFirst ? -15.5 : -14.5,
                          marginTop: 5,
                          boxShadow: isFirst ? `0 0 8px ${color}` : "none",
                        }}
                      />
                      <div className="flex-1 min-w-0" style={{ marginLeft: -2 }}>
                        <span
                          style={{
                            display: "block",
                            fontFamily: "Georgia, serif",
                            fontSize: "13px",
                            fontWeight: 500,
                            color: isLight ? "#5c4030" : "var(--foreground-secondary)",
                            lineHeight: 1.3,
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                        >
                          {item.label}
                        </span>
                        <span
                          className="flex items-center gap-1.5"
                          style={{
                            fontFamily: "Georgia, serif",
                            fontStyle: "italic",
                            fontSize: "11px",
                            color: isLight ? "#9c9484" : "var(--foreground-muted)",
                            lineHeight: 1.3,
                          }}
                        >
                          <span>{ACTIVITY_LABELS[item.activityType] || item.sub}</span>
                          <span style={{ opacity: 0.5 }}>·</span>
                          <span className="font-mono not-italic" style={{ fontSize: "10px" }}>
                            {relativeTime(item.ts)}
                          </span>
                        </span>
                      </div>
                    </div>
                  );
                  return (
                    <div key={item.key}>
                      {item.href ? (
                        <Link
                          href={item.href}
                          style={{ textDecoration: "none" }}
                          onClick={() => setActivityOpen(false)}
                        >
                          {content}
                        </Link>
                      ) : (
                        content
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Team flag picker */}
        <div
          className="relative flex items-center shrink-0"
          ref={teamPickerRef}
          style={{
            paddingLeft: 10,
            borderLeft: `1px solid ${border}`,
          }}
        >
          <button
            className="flex items-center justify-center cursor-pointer focus:outline-none"
            style={{
              width: 32,
              height: 18,
              borderRadius: 4,
              padding: 0,
              border: `1.5px solid ${teamPickerOpen ? accentBorder : border}`,
              backgroundColor: "transparent",
              transition: "border-color 200ms",
              overflow: "hidden",
            }}
            onClick={() => setTeamPickerOpen((v) => !v)}
            aria-label={`Team: ${team.name}`}
            title={team.name}
          >
            <span
              aria-hidden
              style={{
                display: "block",
                width: "100%",
                height: "100%",
                background: `linear-gradient(90deg, ${team.primary} 0%, ${team.primary} 50%, ${team.secondary} 50%, ${team.secondary} 100%)`,
              }}
            />
          </button>

          {teamPickerOpen && (
            <div
              className="absolute light-scrollbar"
              style={{
                top: "calc(100% + 8px)",
                right: 0,
                width: 220,
                maxHeight: 360,
                overflowY: "auto",
                backgroundColor: bg,
                border: `1px solid ${border}`,
                borderRadius: 8,
                boxShadow: isLight
                  ? "0 8px 24px rgba(28,26,20,0.10)"
                  : "0 8px 24px rgba(0,0,0,0.35)",
                padding: "6px",
                zIndex: 10,
              }}
            >
              {TEAMS.map((t) => {
                const isSelected = t.slug === teamSlug;
                return (
                  <button
                    key={t.slug}
                    className="flex items-center gap-2 w-full cursor-pointer focus:outline-none"
                    style={{
                      padding: "6px 8px",
                      borderRadius: 6,
                      border: "none",
                      background: isSelected ? accentBg : "transparent",
                      transition: "background-color 150ms",
                    }}
                    onClick={() => {
                      setTeam(t.slug);
                      setTeamPickerOpen(false);
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = accentBg;
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) e.currentTarget.style.backgroundColor = "transparent";
                    }}
                    aria-label={t.name}
                  >
                    <span
                      aria-hidden
                      style={{
                        flexShrink: 0,
                        display: "block",
                        width: 28,
                        height: 16,
                        borderRadius: 3,
                        border: `1px solid ${border}`,
                        background: `linear-gradient(90deg, ${t.primary} 0%, ${t.primary} 50%, ${t.secondary} 50%, ${t.secondary} 100%)`,
                      }}
                    />
                    <span
                      className="text-[12px]"
                      style={{
                        fontFamily: "Georgia, serif",
                        color: isSelected ? accent : labelHover,
                        fontWeight: isSelected ? 600 : 400,
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                      }}
                    >
                      {t.short}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Theme switcher */}
        <div
          className="flex items-center gap-1 shrink-0"
          style={{
            paddingLeft: 10,
            borderLeft: `1px solid ${border}`,
          }}
        >
          {(
            [
              { key: "light" as const, icon: Sun, label: "Home" },
              { key: "dark" as const, icon: Moon, label: "Away" },
            ]
          ).map(({ key, icon: Icon, label }) => {
            const isSelected = mode === key;
            return (
              <button
                key={key}
                className="flex items-center justify-center rounded-full cursor-pointer focus:outline-none"
                style={{
                  width: 26,
                  height: 26,
                  backgroundColor: isSelected ? accentBg : "transparent",
                  border: `1.5px solid ${isSelected ? accentBorder : "transparent"}`,
                  transition: "border-color 200ms, background-color 200ms",
                }}
                onClick={() => setMode(key)}
                aria-label={label}
                title={label}
              >
                <Icon
                  size={12}
                  style={{
                    color: isSelected ? accent : labelDim,
                    transition: "color 200ms",
                  }}
                />
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
}
