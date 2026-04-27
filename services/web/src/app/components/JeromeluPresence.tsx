"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useTheme } from "./ThemeContext";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import JeromeluLogo from "./JeromeluLogo";
import { LatestThought } from "./LatestThought";
import { ActivityPulse } from "./ActivityPulse";
import { usePageTransition, CONTENT_DELAY_MS, CONTENT_FADE_MS } from "./TransitionContext";
import {
  Activity,
  Newspaper,
  FileText,
  BookOpen,
  MessageCircle,
  Radio,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

// Hero shows the first 5 nav items (one per HERO_ANGLES position).
// The full 6-item nav lives in JeromeluTopBar on inner pages.
const NAV_ITEMS: NavItem[] = [
  { label: "The Feed", href: "/", icon: Activity },
  { label: "The Wiki", href: "/wiki", icon: FileText },
  { label: "The Ledger", href: "/ledger", icon: BookOpen },
  { label: "The Analysis", href: "/insights", icon: Newspaper },
  { label: "Ask Me", href: "/ask", icon: MessageCircle },
  { label: "Live Pulse", href: "/pulse", icon: Radio },
];

// ── Hero (landing page) orbital layout ──
const HERO_AVATAR = 180;
const HERO_DOT = 60;
const HERO_GAP = 50;
const HERO_ICON = 20;
const HERO_ANGLES = [170, 132, 90, 48, 10];
const CONNECTOR_SIZES = [5, 11];

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

// ── Theme colours ──
const DARK_THEME = {
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
  tooltipBg: "var(--accent-bg)",
  tooltipBorder: "var(--accent-border)",
  tooltipColor: "var(--accent)",
};

const LIGHT_THEME = {
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
  tooltipBg: "rgba(120,60,30,0.08)",
  tooltipBorder: "rgba(120,60,30,0.18)",
  tooltipColor: "#5c4030",
};

export function JeromeluPresence() {
  const pathname = usePathname();
  const router = useRouter();
  const { isLight } = useTheme();
  const { triggerClip } = useAvatarEngine();
  const { isTransitioning } = usePageTransition();
  const isHome = pathname === "/landing";

  // Hooks must run unconditionally — early-return after declarations.
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [avatarGlow, setAvatarGlow] = useState(false);
  const [logoKey, setLogoKey] = useState(0);
  const [visibleElements, setVisibleElements] = useState<Set<string>>(new Set());
  const [glowElements, setGlowElements] = useState<Set<string>>(new Set());
  const hasEnteredRef = useRef(false);

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
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Route changes — replay hero entrance whenever we land on /landing
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) { isInitialMount.current = false; return; }
    if (isHome) {
      setVisibleElements(new Set());
      setGlowElements(new Set());
      const sweepStart = CONTENT_DELAY_MS + CONTENT_FADE_MS + 200;
      const timeouts = runHeroEntrance(sweepStart);
      const logoTimer = setTimeout(() => setLogoKey((k) => k + 1), sweepStart);
      return () => { timeouts.forEach(clearTimeout); clearTimeout(logoTimer); };
    }
    setVisibleElements(new Set());
    setGlowElements(new Set());
  }, [isHome, runHeroEntrance]);

  const handleBubbleHover = useCallback((index: number) => {
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
  }, [triggerClip]);

  const handleLeave = useCallback(() => {
    setHoveredIndex(null);
    setAvatarGlow(false);
  }, []);

  const heroAvatarRadius = HERO_AVATAR / 2;
  const heroOrbitRadius = heroAvatarRadius + HERO_GAP + HERO_DOT / 2;
  const heroClusterSize = (heroOrbitRadius + HERO_DOT / 2 + 8) * 2;
  const heroCenter = heroClusterSize / 2;

  // JeromeluPresence now exists only to render the landing-page orbital hero.
  // Inner-page chrome lives in JeromeluTopBar.
  if (!isHome) return null;

  const theme = isLight ? LIGHT_THEME : DARK_THEME;

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
        {NAV_ITEMS.slice(0, 5).map((_, i) => {
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
                  boxShadow: isGlowing ? `0 0 8px ${theme.connectorGlow}` : "none",
                  opacity: isConnVisible ? 1 : 0,
                  transform: isConnVisible ? "scale(1)" : "scale(0)",
                  transition: "opacity 200ms, transform 200ms, background-color 200ms, box-shadow 200ms",
                }}
              />
            );
          });
        })}

        {/* Orbital nav bubbles */}
        {NAV_ITEMS.slice(0, 5).map((item, i) => {
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
                  boxShadow: isBubbleGlowing ? theme.bubbleShadowActive : "none",
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
        <div className="mt-6"><LatestThought /></div>
        <div className="mt-3"><ActivityPulse /></div>
      </div>
    </div>
  );
}
