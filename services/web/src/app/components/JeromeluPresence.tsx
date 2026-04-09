"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "./ThemeContext";
import type { WikiChangeItem } from "../wiki/wiki-data";
import type { FeedItem, FeedResponse } from "../feed/feed-data";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import JeromeluLogo, { LETTERS } from "./JeromeluLogo";
import { CrewStatus } from "./CrewStatus";
import { LatestThought } from "./LatestThought";
import { ActivityPulse } from "./ActivityPulse";
import { usePageTransition, TRANSITION_DURATION_MS, CONTENT_DELAY_MS, CONTENT_FADE_MS } from "./TransitionContext";
import {
  Activity,
  Newspaper,
  FileText,
  BookOpen,
  MessageCircle,
  Sun,
  Moon,
  Monitor,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

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
];

// ── Hero (landing page) orbital layout ──
const HERO_AVATAR = 180;
const HERO_DOT = 60;
const HERO_GAP = 50;
const HERO_ICON = 20;
const HERO_ANGLES = [170, 132, 90, 48, 10];
const CONNECTOR_SIZES = [5, 11];

// ── Inner pages sidebar layout ──
const INNER_AVATAR = 160;
const SIDEBAR_WIDTH = 240;
const SIDEBAR_DOT = 34;
const SIDEBAR_ICON = 15;

const T = `${TRANSITION_DURATION_MS}ms cubic-bezier(0.4, 0, 0.2, 1)`;

// Activity type → accent color
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

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

// ── Theme colours ──
const DARK_THEME = {
  // Orbital bubbles (home)
  bubbleBg: "rgba(255,255,255,0.10)",
  bubbleBorder: "rgba(255,255,255,0.18)",
  bubbleBgActive: "rgba(212,135,74,0.12)",
  bubbleBorderActive: "rgba(212,135,74,0.5)",
  bubbleIcon: "rgba(255,255,255,0.55)",
  bubbleIconActive: "var(--accent)",
  bubbleShadowActive: "0 0 16px rgba(212,135,74,0.25)",
  connectorDefault: "rgba(255,255,255,0.08)",
  connectorHover: "rgba(212,135,74,0.35)",
  connectorGlow: "rgba(212,135,74,0.8)",
  // Sidebar (inner pages)
  dotBg: "transparent",
  dotBorder: "var(--border-subtle)",
  dotBgActive: "var(--accent-bg)",
  dotBorderActive: "var(--accent-glow)",
  icon: "var(--foreground-muted)",
  iconActive: "var(--accent)",
  label: "var(--foreground-muted)",
  labelActive: "var(--accent)",
  labelHover: "var(--foreground-secondary)",
  shadowActive: "0 0 12px var(--accent-border)",
  // Shared
  onlineDot: "var(--tigers-orange)",
  onlineText: "var(--foreground-muted)",
  tooltipBg: "var(--accent-bg)",
  tooltipBorder: "var(--accent-border)",
  tooltipColor: "var(--accent)",
};

const LIGHT_THEME = {
  // Orbital bubbles (home — not currently used since home is dark, but for completeness)
  bubbleBg: "rgba(120,60,30,0.08)",
  bubbleBorder: "rgba(120,60,30,0.22)",
  bubbleBgActive: "rgba(120,60,30,0.14)",
  bubbleBorderActive: "rgba(120,60,30,0.50)",
  bubbleIcon: "rgba(92,64,48,0.55)",
  bubbleIconActive: "#8b4513",
  bubbleShadowActive: "0 2px 8px rgba(120,60,30,0.20)",
  connectorDefault: "rgba(120,60,30,0.18)",
  connectorHover: "rgba(120,60,30,0.45)",
  connectorGlow: "rgba(120,60,30,0.70)",
  // Sidebar (inner pages)
  dotBg: "transparent",
  dotBorder: "rgba(120,60,30,0.22)",
  dotBgActive: "rgba(120,60,30,0.14)",
  dotBorderActive: "rgba(120,60,30,0.50)",
  icon: "rgba(92,64,48,0.50)",
  iconActive: "#8b4513",
  label: "rgba(92,64,48,0.55)",
  labelActive: "#8b4513",
  labelHover: "#5c4030",
  shadowActive: "0 2px 6px rgba(120,60,30,0.18)",
  // Shared
  onlineDot: "#5c4030",
  onlineText: "#7a7060",
  tooltipBg: "rgba(120,60,30,0.08)",
  tooltipBorder: "rgba(120,60,30,0.18)",
  tooltipColor: "#5c4030",
};

export function JeromeluPresence() {
  const pathname = usePathname();
  const router = useRouter();
  const { mode, setMode, isLight } = useTheme();
  const { triggerClip } = useAvatarEngine();
  const { isTransitioning } = usePageTransition();
  const isHome = pathname === "/landing";
  const isAdmin = pathname.startsWith("/admin");
  const isStream = pathname.startsWith("/stream");

  if (isAdmin || isStream) return null;

  const theme = isLight ? LIGHT_THEME : DARK_THEME;
  const avatarSize = isHome ? HERO_AVATAR : INNER_AVATAR;

  // ── Recent activity (feed + wiki changes) ──
  type ActivityItem = { key: string; label: string; sub: string; activityType: string; href?: string; ts: string };
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [activityExpanded, setActivityExpanded] = useState(false);
  const [ringPulseColor, setRingPulseColor] = useState<string | null>(null);
  useEffect(() => {
    if (isHome) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL!;
    const ACTIVITY_TYPES = new Set(["watching", "signal", "thinking", "prediction", "action", "review", "sys"]);

    Promise.allSettled([
      fetch(`${apiBase}/api/feed?limit=20`).then((r) => r.json()) as Promise<FeedResponse>,
      fetch(`${apiBase}/api/wiki/recent-changes?limit=10`).then((r) => r.json()) as Promise<{ items: WikiChangeItem[] }>,
    ]).then(([feedResult, wikiResult]) => {
      const items: ActivityItem[] = [];

      // Feed activity (non-chat)
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

      // Wiki changes
      if (wikiResult.status === "fulfilled") {
        for (const wc of (wikiResult.value.items || [])) {
          const href = wc.page_type === "round"
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

      // Sort newest first, take top 15
      items.sort((a, b) => (b.ts || "").localeCompare(a.ts || ""));
      const top = items.slice(0, 15);
      setRecentActivity(top);

      // Pulse the avatar ring with the color of the most recent activity
      if (top.length > 0) {
        const color = ACTIVITY_COLORS[top[0].activityType] || ACTIVITY_COLORS.watching;
        setRingPulseColor(color);
        setTimeout(() => setRingPulseColor(null), 2000);
      }
    });
  }, [isHome]);

  // ── Shared state ──
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [avatarGlow, setAvatarGlow] = useState(false);
  const [logoKey, setLogoKey] = useState(0);

  // ── Hero orbital entrance state ──
  const [visibleElements, setVisibleElements] = useState<Set<string>>(new Set());
  const [glowElements, setGlowElements] = useState<Set<string>>(new Set());
  const hasEnteredRef = useRef(false);

  // ── Sidebar state ──
  const [sidebarHovered, setSidebarHovered] = useState(false);
  const [sidebarVisibleCount, setSidebarVisibleCount] = useState(0);
  // ── Sidebar logo sweep animation ──
  // Same outside-in pattern as the landing page JeromeluLogo
  const OUTSIDE_IN = useMemo(() => [0, 7, 1, 6, 2, 5, 3, 4], []);
  const [litLetters, setLitLetters] = useState<Set<number>>(new Set());
  const sweepTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  const runLogoSweep = useCallback(() => {
    // Clear any running sweep
    sweepTimersRef.current.forEach(clearTimeout);
    sweepTimersRef.current = [];
    setLitLetters(new Set());

    const STAGGER = 80;
    const allLitAt = OUTSIDE_IN.length * STAGGER;
    const pause = 300;

    // Phase 1: orange sweeps in from both ends
    OUTSIDE_IN.forEach((letterIndex, step) => {
      sweepTimersRef.current.push(setTimeout(() => {
        setLitLetters((prev) => new Set(prev).add(letterIndex));
      }, step * STAGGER));
    });

    // Phase 2: sweep back out (remove glow)
    OUTSIDE_IN.forEach((letterIndex, step) => {
      sweepTimersRef.current.push(setTimeout(() => {
        setLitLetters((prev) => { const n = new Set(prev); n.delete(letterIndex); return n; });
      }, allLitAt + pause + step * STAGGER));
    });
  }, [OUTSIDE_IN]);

  // All orbital element keys
  const allOrbitalElements = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < 5; i++) {
      s.add(`conn-${i}-0`);
      s.add(`conn-${i}-1`);
      s.add(`bubble-${i}`);
    }
    return s;
  }, []);

  // Hero entrance: stagger bubbles outward with glow sweep
  const runHeroEntrance = useCallback((startDelay: number) => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const STEP_MS = 210;
    const PHASE2_START = 940;
    const PHASE2_STEP = 210;

    for (let i = 0; i < 5; i++) {
      const connSmallKey = `conn-${i}-0`;
      const connLargeKey = `conn-${i}-1`;
      const bubbleKey = `bubble-${i}`;

      timeouts.push(setTimeout(() => {
        setVisibleElements((prev) => new Set(prev).add(connSmallKey));
        setGlowElements((prev) => new Set(prev).add(connSmallKey));
      }, startDelay));

      timeouts.push(setTimeout(() => {
        setVisibleElements((prev) => new Set(prev).add(connLargeKey));
        setGlowElements((prev) => new Set(prev).add(connLargeKey));
      }, startDelay + STEP_MS));

      timeouts.push(setTimeout(() => {
        setVisibleElements((prev) => new Set(prev).add(bubbleKey));
        setGlowElements((prev) => new Set(prev).add(bubbleKey));
      }, startDelay + STEP_MS * 2));

      // Phase 2: remove glow
      timeouts.push(setTimeout(() => {
        setGlowElements((prev) => { const n = new Set(prev); n.delete(bubbleKey); return n; });
      }, startDelay + PHASE2_START));

      timeouts.push(setTimeout(() => {
        setGlowElements((prev) => { const n = new Set(prev); n.delete(connLargeKey); return n; });
      }, startDelay + PHASE2_START + PHASE2_STEP));

      timeouts.push(setTimeout(() => {
        setGlowElements((prev) => { const n = new Set(prev); n.delete(connSmallKey); return n; });
      }, startDelay + PHASE2_START + PHASE2_STEP * 2));
    }

    return timeouts;
  }, []);

  // Initial entrance
  useEffect(() => {
    if (hasEnteredRef.current) return;
    hasEnteredRef.current = true;

    if (isHome) {
      const timeouts = runHeroEntrance(0);
      return () => timeouts.forEach(clearTimeout);
    } else {
      setSidebarVisibleCount(NAV_ITEMS.length);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Route changes: toggle between hero and sidebar
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) { isInitialMount.current = false; return; }
    if (isHome) {
      // Arriving at home — reset and replay hero entrance
      setSidebarVisibleCount(0);
      setVisibleElements(new Set());
      setGlowElements(new Set());
      const sweepStart = CONTENT_DELAY_MS + CONTENT_FADE_MS + 200;
      const timeouts = runHeroEntrance(sweepStart);
      const logoTimer = setTimeout(() => setLogoKey((k) => k + 1), sweepStart);
      return () => { timeouts.forEach(clearTimeout); clearTimeout(logoTimer); };
    } else {
      // Leaving home — show sidebar immediately
      setVisibleElements(new Set());
      setGlowElements(new Set());
      setSidebarVisibleCount(NAV_ITEMS.length);
    }
  }, [isHome, runHeroEntrance]);

  // ── Hero: orbital bubble hover ──
  const handleBubbleHover = (index: number) => {
    setHoveredIndex(index);
    setAvatarGlow(true);
    const angle = HERO_ANGLES[index];
    if (angle > 90 && angle < 270) {
      triggerClip("directional", "glance-left");
    } else if (angle < 90 || angle > 270) {
      triggerClip("directional", "glance-right");
    } else {
      triggerClip("directional", "glance-up");
    }
  };

  // ── Sidebar: nav item hover ──
  const handleSidebarHover = (index: number) => {
    setHoveredIndex(index);
    setAvatarGlow(true);
    triggerClip("directional", "glance-down");
  };

  const handleLeave = () => {
    setHoveredIndex(null);
    setAvatarGlow(false);
  };

  // ── Hero orbital layout calculations ──
  const heroAvatarRadius = HERO_AVATAR / 2;
  const heroOrbitRadius = heroAvatarRadius + HERO_GAP + HERO_DOT / 2;
  const heroClusterSize = (heroOrbitRadius + HERO_DOT / 2 + 8) * 2;
  const heroCenter = heroClusterSize / 2;

  // ════════════════════════════════════════════
  //  RENDER: HOME (orbital arc)
  // ════════════════════════════════════════════
  if (isHome) {
    return (
      <div
        className="fixed z-50 pointer-events-none"
        style={{
          top: "50%",
          left: "50%",
          transform: "translate(-50%, -50%)",
        }}
      >
        {/* Orbital cluster */}
        <div
          className="relative pointer-events-auto"
          style={{ width: heroClusterSize, height: heroClusterSize }}
          onMouseLeave={handleLeave}
        >
          {/* Avatar */}
          <div
            className="absolute rounded-full"
            style={{
              left: heroCenter - HERO_AVATAR / 2,
              top: heroCenter - HERO_AVATAR / 2,
              transition: `box-shadow 300ms ease`,
              boxShadow: avatarGlow
                ? "0 0 24px 8px rgba(212,135,74,0.4), 0 0 48px 16px rgba(212,135,74,0.15)"
                : "none",
            }}
          >
            <ConnectedAvatar size={HERO_AVATAR} />
          </div>

          {/* Connector dots */}
          {NAV_ITEMS.map((_, i) => {
            const angleRad = toRad(HERO_ANGLES[i]);
            return CONNECTOR_SIZES.map((dotSz, ci) => {
              const connKey = `conn-${i}-${ci}`;
              const isConnVisible = visibleElements.has(connKey);
              const isGlowing = glowElements.has(connKey);
              const t = 0.3 + ci * 0.25;
              const startDist = heroAvatarRadius + 4;
              const endDist = heroOrbitRadius - HERO_DOT / 2 - 4;
              const dist = startDist + t * (endDist - startDist);
              return (
                <div
                  key={`c-${i}-${ci}`}
                  className="absolute rounded-full"
                  style={{
                    left: heroCenter + dist * Math.cos(angleRad) - dotSz / 2,
                    top: heroCenter - dist * Math.sin(angleRad) - dotSz / 2,
                    width: dotSz,
                    height: dotSz,
                    backgroundColor:
                      isGlowing
                        ? theme.connectorGlow
                        : hoveredIndex === i
                          ? theme.connectorHover
                          : theme.connectorDefault,
                    boxShadow: isGlowing
                      ? `0 0 8px ${theme.connectorGlow}`
                      : "none",
                    opacity: isConnVisible ? 1 : 0,
                    transform: isConnVisible ? "scale(1)" : "scale(0)",
                    transition: "opacity 200ms, transform 200ms, background-color 200ms, box-shadow 200ms",
                  }}
                />
              );
            });
          })}

          {/* Orbital nav bubbles */}
          {NAV_ITEMS.map((item, i) => {
            const angleRad = toRad(HERO_ANGLES[i]);
            const isHovered = hoveredIndex === i;
            const bubbleKey = `bubble-${i}`;
            const isVisible = visibleElements.has(bubbleKey);
            const isBubbleGlowing = glowElements.has(bubbleKey);
            const Icon = item.icon;

            const x = heroCenter + heroOrbitRadius * Math.cos(angleRad) - HERO_DOT / 2;
            const y = heroCenter - heroOrbitRadius * Math.sin(angleRad) - HERO_DOT / 2;

            // Tooltip positioning
            const angle = HERO_ANGLES[i];
            const bubbleCenterX = heroCenter + heroOrbitRadius * Math.cos(angleRad);
            const bubbleCenterY = heroCenter - heroOrbitRadius * Math.sin(angleRad);
            let tooltipX = bubbleCenterX;
            let tooltipY = bubbleCenterY;
            let tooltipTransform = "translate(-50%, -100%)";

            if (angle > 110 && angle < 135) {
              tooltipX -= HERO_DOT / 2 + 8;
              tooltipTransform = "translate(-100%, -50%)";
            } else if (angle > 45 && angle < 70) {
              tooltipX += HERO_DOT / 2 + 8;
              tooltipTransform = "translate(0%, -50%)";
            } else if (angle >= 70 && angle <= 110) {
              tooltipY -= HERO_DOT / 2 + 8;
              tooltipTransform = "translate(-50%, -100%)";
            } else if (angle >= 135 && angle <= 225) {
              tooltipX -= HERO_DOT / 2 + 8;
              tooltipTransform = "translate(-100%, -50%)";
            } else {
              tooltipX += HERO_DOT / 2 + 8;
              tooltipTransform = "translate(0%, -50%)";
            }

            return (
              <div key={item.href}>
                <button
                  className="absolute flex items-center justify-center rounded-full cursor-pointer focus:outline-none"
                  style={{
                    left: x,
                    top: y,
                    width: HERO_DOT,
                    height: HERO_DOT,
                    backgroundColor:
                      isHovered || isBubbleGlowing
                        ? theme.bubbleBgActive
                        : theme.bubbleBg,
                    border:
                      isHovered || isBubbleGlowing
                        ? `1.5px solid ${theme.bubbleBorderActive}`
                        : `1.5px solid ${theme.bubbleBorder}`,
                    boxShadow: isBubbleGlowing
                      ? theme.bubbleShadowActive
                      : "none",
                    transform: isVisible
                      ? isHovered ? "scale(1.15)" : "scale(1)"
                      : "scale(0)",
                    opacity: isVisible ? 1 : 0,
                    animation: isVisible
                      ? `thought-float 3s ease-in-out ${i * 0.4}s infinite`
                      : "none",
                    transition: "opacity 200ms, background-color 300ms, border 300ms, box-shadow 300ms, transform 200ms",
                  }}
                  onClick={() => router.push(item.href)}
                  onMouseEnter={() => handleBubbleHover(i)}
                  onMouseLeave={handleLeave}
                  aria-label={item.label}
                >
                  <Icon
                    size={HERO_ICON}
                    style={{
                      color: isHovered || isBubbleGlowing
                        ? theme.bubbleIconActive
                        : theme.bubbleIcon,
                      transition: "color 300ms",
                    }}
                  />
                </button>

                {/* Tooltip */}
                {isHovered && isVisible && (
                  <div
                    className="absolute whitespace-nowrap rounded-md px-2.5 py-1 text-[11px] font-medium pointer-events-none"
                    style={{
                      left: tooltipX,
                      top: tooltipY,
                      transform: tooltipTransform,
                      backgroundColor: theme.tooltipBg,
                      color: theme.tooltipColor,
                      border: `1px solid ${theme.tooltipBorder}`,
                    }}
                  >
                    {item.label}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Hero content below cluster */}
        <div
          className="flex flex-col items-center text-center"
          style={{
            marginTop: -100,
            width: heroClusterSize,
            opacity: !isTransitioning ? 1 : 0,
            transition: `opacity ${CONTENT_FADE_MS}ms ease-in ${CONTENT_DELAY_MS}ms`,
            pointerEvents: "auto",
          }}
        >
          <JeromeluLogo key={logoKey} />
          <div className="mt-6"><CrewStatus /></div>
          <div className="mt-4"><LatestThought /></div>
          <div className="mt-3"><ActivityPulse /></div>
        </div>
      </div>
    );
  }

  // ════════════════════════════════════════════
  //  RENDER: INNER PAGES (sidebar nav)
  // ════════════════════════════════════════════
  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{ top: 0, left: 0, bottom: 0, width: 300, paddingTop: 24, paddingLeft: 30, paddingRight: 30, paddingBottom: 24 }}
    >
      <div
        className="flex flex-col items-center pointer-events-auto h-full"
        style={{ width: SIDEBAR_WIDTH }}
        onMouseEnter={() => setSidebarHovered(true)}
        onMouseLeave={() => {
          setSidebarHovered(false);
          handleLeave();
        }}
      >
        {/* Logo — "Jaromelu" with orange sweep animation */}
        <div
          className="flex items-center gap-0 mb-3 cursor-pointer select-none"
          onClick={() => { router.push("/landing"); }}
          onMouseEnter={runLogoSweep}
        >
          {LETTERS.map((letter, i) => {
            const isLit = litLetters.has(i);
            return (
              <span
                key={i}
                className="text-3xl font-bold tracking-tight"
                style={{
                  padding: "0 0.5px",
                  color: isLit
                    ? isLight ? "#b85c38" : "var(--accent)"
                    : isLight ? "rgba(92,64,48,0.35)" : "var(--foreground-muted)",
                  textShadow: isLit
                    ? isLight
                      ? "0 0 10px rgba(184,92,56,0.3)"
                      : "0 0 14px var(--accent-glow), 0 0 28px var(--accent-glow)"
                    : "none",
                  transition: "color 200ms, text-shadow 200ms",
                }}
              >
                {letter.char}
              </span>
            );
          })}
        </div>

        {/* Avatar with ring pulse */}
        <div
          className="rounded-full relative"
          style={{
            transition: "box-shadow 600ms ease",
            boxShadow: ringPulseColor
              ? `0 0 20px 6px ${ringPulseColor}, 0 0 40px 12px color-mix(in srgb, ${ringPulseColor} 30%, transparent)`
              : avatarGlow
                ? isLight
                  ? "0 2px 12px rgba(120,60,30,0.25), 0 0 0 2px rgba(120,60,30,0.12)"
                  : "0 0 24px 8px rgba(212,135,74,0.4), 0 0 48px 16px rgba(212,135,74,0.15)"
                : "none",
          }}
        >
          <ConnectedAvatar size={INNER_AVATAR} light={isLight} />
        </div>

        {/* Live status — click to expand/collapse activity */}
        <button
          className="flex items-center justify-center gap-1.5 font-mono text-[10px] mt-4 cursor-pointer focus:outline-none"
          style={{
            opacity: sidebarHovered ? 1 : 0.6,
            transition: "opacity 300ms",
            background: "none",
            border: "none",
            padding: "2px 0",
          }}
          onClick={() => setActivityExpanded((prev) => !prev)}
          title={activityExpanded ? "Collapse activity" : "Expand activity"}
        >
          <span className="relative flex h-1.5 w-1.5 shrink-0">
            <span
              className="absolute inline-flex h-full w-full animate-ping rounded-full opacity-75"
              style={{ backgroundColor: recentActivity.length > 0 ? (ACTIVITY_COLORS[recentActivity[0].activityType] || theme.onlineDot) : theme.onlineDot }}
            />
            <span
              className="relative inline-flex h-1.5 w-1.5 rounded-full"
              style={{ backgroundColor: recentActivity.length > 0 ? (ACTIVITY_COLORS[recentActivity[0].activityType] || theme.onlineDot) : theme.onlineDot }}
            />
          </span>
          <span
            className="whitespace-nowrap overflow-hidden text-ellipsis"
            style={{
              color: theme.onlineText,
              maxWidth: SIDEBAR_WIDTH - 20,
            }}
          >
            {recentActivity.length > 0
              ? `${ACTIVITY_LABELS[recentActivity[0].activityType] || recentActivity[0].activityType} · ${relativeTime(recentActivity[0].ts)}`
              : "online"}
          </span>
          <span
            style={{
              fontSize: "8px",
              color: theme.onlineText,
              transform: activityExpanded ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 200ms",
              marginLeft: 2,
            }}
          >
            ▾
          </span>
        </button>

        {/* Timeline thread — collapsible, directly below status */}
        <div
          className="w-full overflow-hidden light-scrollbar"
          style={{
            maxHeight: activityExpanded ? 220 : 0,
            opacity: activityExpanded ? 1 : 0,
            marginTop: activityExpanded ? 6 : 0,
            transition: "max-height 350ms cubic-bezier(0.4, 0, 0.2, 1), opacity 250ms ease, margin-top 250ms ease",
            overflowY: activityExpanded ? "auto" : "hidden",
          }}
        >
          {recentActivity.length > 0 && (
            <div className="relative" style={{ paddingLeft: 14 }}>
              {/* Vertical thread line */}
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
                  animation: activityExpanded ? "timeline-line-grow 400ms ease-out forwards" : "none",
                }}
              />

              {recentActivity.map((item, i) => {
                const color = ACTIVITY_COLORS[item.activityType] || ACTIVITY_COLORS.watching;
                const isFirst = i === 0;
                const content = (
                  <div
                    className="flex items-start gap-2.5 py-1.5"
                    style={{
                      animation: activityExpanded ? `timeline-reveal 300ms ease-out ${i * 60}ms both` : "none",
                    }}
                  >
                    {/* Timeline dot — positioned over the thread line */}
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
                    {/* Text content */}
                    <div className="flex-1 min-w-0" style={{ marginLeft: -2 }}>
                      <span
                        style={{
                          display: "block",
                          fontSize: "11px",
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
                          fontSize: "10px",
                          color: isLight ? "#9c9484" : "var(--foreground-muted)",
                          lineHeight: 1.3,
                        }}
                      >
                        <span>{ACTIVITY_LABELS[item.activityType] || item.sub}</span>
                        <span style={{ opacity: 0.5 }}>·</span>
                        <span className="font-mono" style={{ fontSize: "9px" }}>
                          {relativeTime(item.ts)}
                        </span>
                      </span>
                    </div>
                  </div>
                );
                return (
                  <div key={item.key}>
                    {item.href ? (
                      <Link href={item.href} style={{ textDecoration: "none" }}>
                        {content}
                      </Link>
                    ) : (
                      content
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Nav items */}
        <nav className="flex flex-col w-full" style={{ marginTop: 16, gap: 2 }}>
          {NAV_ITEMS.map((item, i) => {
            const isActive = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
            const isHovered = hoveredIndex === i;
            const isVisible = i < sidebarVisibleCount;
            const Icon = item.icon;

            return (
              <button
                key={item.href}
                className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 cursor-pointer focus:outline-none"
                style={{
                  opacity: isVisible ? 1 : 0,
                  transform: isVisible ? "translateY(0)" : "translateY(8px)",
                  transition: "opacity 200ms ease, transform 200ms ease, background-color 200ms, box-shadow 200ms",
                  backgroundColor: isActive || isHovered ? theme.dotBgActive : "transparent",
                  boxShadow: isActive ? theme.shadowActive : "none",
                }}
                onClick={() => router.push(item.href)}
                onMouseEnter={() => handleSidebarHover(i)}
                onMouseLeave={handleLeave}
              >
                <span
                  className="flex items-center justify-center rounded-full shrink-0"
                  style={{
                    width: SIDEBAR_DOT,
                    height: SIDEBAR_DOT,
                    border: `1.5px solid ${isActive || isHovered ? theme.dotBorderActive : theme.dotBorder}`,
                    backgroundColor: isActive ? theme.dotBgActive : "transparent",
                    transition: "border-color 200ms, background-color 200ms",
                  }}
                >
                  <Icon
                    size={SIDEBAR_ICON}
                    style={{
                      color: isActive || isHovered ? theme.iconActive : theme.icon,
                      transition: "color 200ms",
                    }}
                  />
                </span>
                <span
                  className="text-[12px] font-medium whitespace-nowrap"
                  style={{
                    letterSpacing: "0.03em",
                    color: isActive ? theme.labelActive : isHovered ? theme.labelHover : theme.label,
                    transition: "color 200ms",
                  }}
                >
                  {item.label}
                </span>
              </button>
            );
          })}
        </nav>

        {/* Theme switcher — pinned to bottom */}
        <div
          className="flex items-center justify-center gap-1 w-full shrink-0 mt-auto"
          style={{
            paddingTop: 10,
            borderTop: isLight ? "1px solid rgba(120,60,30,0.12)" : "1px solid var(--border)",
          }}
        >
          {([
            { key: "auto" as const, icon: Monitor, label: "Auto" },
            { key: "light" as const, icon: Sun, label: "Light" },
            { key: "dark" as const, icon: Moon, label: "Dark" },
          ]).map(({ key, icon: Icon, label }) => {
            const isSelected = mode === key;
            return (
              <button
                key={key}
                className="flex items-center justify-center rounded-full cursor-pointer focus:outline-none"
                style={{
                  width: 28,
                  height: 28,
                  backgroundColor: isSelected
                    ? isLight ? "rgba(120,60,30,0.14)" : "var(--accent-bg)"
                    : "transparent",
                  border: `1.5px solid ${isSelected
                    ? isLight ? "rgba(120,60,30,0.50)" : "var(--accent-glow)"
                    : "transparent"}`,
                  transition: "border-color 200ms, background-color 200ms",
                }}
                onClick={() => setMode(key)}
                aria-label={label}
                title={label}
              >
                <Icon
                  size={13}
                  style={{
                    color: isSelected
                      ? isLight ? "#8b4513" : "var(--accent)"
                      : isLight ? "rgba(92,64,48,0.40)" : "var(--foreground-muted)",
                    transition: "color 200ms",
                  }}
                />
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
