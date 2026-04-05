"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import JeromeluLogo from "./JeromeluLogo";
import { CrewStatus } from "./CrewStatus";
import { LatestThought } from "./LatestThought";
import { ActivityPulse } from "./ActivityPulse";
import { usePageTransition, TRANSITION_DURATION_MS, CONTENT_DELAY_MS, CONTENT_FADE_MS } from "./TransitionContext";
import {
  Activity,
  Users,
  FileText,
  BookOpen,
  MessageCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavBubble {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV_BUBBLES: NavBubble[] = [
  { label: "The Feed", href: "/feed", icon: Activity },
  { label: "My Squad", href: "/squad", icon: Users },
  { label: "The Dossier", href: "/dossier", icon: FileText },
  { label: "The Ledger", href: "/ledger", icon: BookOpen },
  { label: "Ask Me", href: "/feed", icon: MessageCircle },
];

// Hero: upper arc (landing — text below needs clearance)
const HERO_ANGLES = [170, 132, 90, 48, 10];
// Orbital: full circle (inner pages — no text, surround the avatar)
const ORBITAL_ANGLES = [162, 90, 18, 306, 234];

// Hero mode (landing page)
const HERO_AVATAR = 180;
const HERO_DOT = 60;
const HERO_GAP = 50;
const HERO_ICON = 20;

// Orbital mode (inner pages)
const ORBITAL_AVATAR = 160;
const ORBITAL_DOT = 42;
const ORBITAL_GAP = 14;
const ORBITAL_ICON = 18;

const CONNECTOR_SIZES = [5, 11];
const ENTRANCE_ORDER = [2, 1, 3, 0, 4];

const T = `${TRANSITION_DURATION_MS}ms cubic-bezier(0.4, 0, 0.2, 1)`;

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

export function JeromeluPresence() {
  const pathname = usePathname();
  const router = useRouter();
  const { triggerClip } = useAvatarEngine();
  const { isTransitioning } = usePageTransition();
  const isHome = pathname === "/";
  const isAdmin = pathname.startsWith("/admin");
  const isStream = pathname.startsWith("/stream");

  // Hide presence on admin and stream pages
  if (isAdmin || isStream) return null;

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [clusterHovered, setClusterHovered] = useState(false);
  // Track visibility per element: "bubble-{i}" for nav bubbles, "conn-{i}-{ci}" for connectors
  const [visibleElements, setVisibleElements] = useState<Set<string>>(new Set());
  // Track which elements are currently in their orange sweep glow
  const [glowElements, setGlowElements] = useState<Set<string>>(new Set());
  const hasEnteredRef = useRef(false);
  const [logoKey, setLogoKey] = useState(0);
  // Hover sequence: connectors glow inward, then avatar pulses
  const [hoverGlowSet, setHoverGlowSet] = useState<Set<string>>(new Set());
  const [avatarGlow, setAvatarGlow] = useState(false);
  const hoverTimersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Synced with JeromeluLogo two-phase sweep:
  //   Logo Phase 1 (orange in):  0–640ms  (8 letters × 80ms)
  //   Logo pause:                640–940ms (300ms)
  //   Logo Phase 2 (white back): 940–1580ms (8 letters × 80ms)
  // Bubbles mirror this with 3 steps (small dot → large dot → bubble):
  //   Phase 1: sweep out (appear + glow)  0–420ms  (3 × 210ms, ending before logo finishes)
  //   Pause:   hold glow until logo Phase 2 starts
  //   Phase 2: sweep back in (remove glow, bubble → large dot → small dot)
  const runBubbleEntrance = useCallback((startDelay: number) => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    const STEP_MS = 210;
    // Logo Phase 2 starts at 940ms — sweep glow off in reverse order to match
    const PHASE2_START = 940;
    const PHASE2_STEP = 210;

    for (let i = 0; i < 5; i++) {
      const connSmallKey = `conn-${i}-0`;
      const connLargeKey = `conn-${i}-1`;
      const bubbleKey = `bubble-${i}`;

      // Phase 1: sweep out — appear + glow on
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

      // Phase 2: sweep back in — remove glow (reverse: bubble → large → small)
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

  // All element keys for "everything visible" state
  const allElements = useMemo(() => {
    const s = new Set<string>();
    for (let i = 0; i < 5; i++) {
      s.add(`conn-${i}-0`);
      s.add(`conn-${i}-1`);
      s.add(`bubble-${i}`);
    }
    return s;
  }, []);

  // Staggered entrance — once only
  useEffect(() => {
    if (hasEnteredRef.current) return;
    hasEnteredRef.current = true;

    if (!isHome) {
      setVisibleElements(allElements);
      return;
    }

    const timeouts = runBubbleEntrance(0);
    return () => timeouts.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ensure all visible when leaving home; replay entrance + logo on return
  const isInitialMount = useRef(true);
  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (!isHome) {
      setVisibleElements(allElements);
      setGlowElements(new Set());
    } else {
      // Reset bubbles for re-entrance, synced with logo remount
      setVisibleElements(new Set());
      setGlowElements(new Set());
      const sweepStart = CONTENT_DELAY_MS + CONTENT_FADE_MS + 200;
      const timeouts = runBubbleEntrance(sweepStart);
      const logoTimer = setTimeout(
        () => setLogoKey((k) => k + 1),
        sweepStart,
      );
      return () => { timeouts.forEach(clearTimeout); clearTimeout(logoTimer); };
    }
  }, [isHome, allElements, runBubbleEntrance]);

  const handleBubbleHover = (index: number) => {
    setHoveredIndex(index);

    // Clear any previous hover timers
    hoverTimersRef.current.forEach(clearTimeout);
    hoverTimersRef.current = [];
    setHoverGlowSet(new Set());
    setAvatarGlow(false);

    const angles = isHome ? HERO_ANGLES : ORBITAL_ANGLES;
    const angle = angles[index];
    if (angle > 90 && angle < 270) {
      triggerClip("directional", "glance-left");
    } else if (angle < 90 || angle > 270) {
      triggerClip("directional", "glance-right");
    } else {
      triggerClip("directional", "glance-up");
    }

    // Sequential glow inward: large connector → small connector → avatar
    const connLargeKey = `conn-${index}-1`;
    const connSmallKey = `conn-${index}-0`;
    const HOVER_STEP = 120;

    hoverTimersRef.current.push(setTimeout(() => {
      setHoverGlowSet((prev) => new Set(prev).add(connLargeKey));
    }, 0));
    hoverTimersRef.current.push(setTimeout(() => {
      setHoverGlowSet((prev) => new Set(prev).add(connSmallKey));
    }, HOVER_STEP));
    hoverTimersRef.current.push(setTimeout(() => {
      setAvatarGlow(true);
    }, HOVER_STEP * 2));
  };

  const handleBubbleLeave = () => {
    setHoveredIndex(null);
    hoverTimersRef.current.forEach(clearTimeout);
    hoverTimersRef.current = [];
    setHoverGlowSet(new Set());
    setAvatarGlow(false);
  };

  // Layout calculations
  const avatarSize = isHome ? HERO_AVATAR : ORBITAL_AVATAR;
  const dotSize = isHome ? HERO_DOT : ORBITAL_DOT;
  const gap = isHome ? HERO_GAP : ORBITAL_GAP;
  const iconSize = isHome ? HERO_ICON : ORBITAL_ICON;
  const angles = isHome ? HERO_ANGLES : ORBITAL_ANGLES;

  const avatarRadius = avatarSize / 2;
  const orbitRadius = avatarRadius + gap + dotSize / 2;
  const clusterSize = (orbitRadius + dotSize / 2 + 8) * 2;
  const center = clusterSize / 2;

  return (
    <div
      className="fixed z-50 pointer-events-none"
      style={{
        top: "50%",
        left: isHome ? "50%" : "calc((100vw - 48rem) / 4)",
        transform: "translate(-50%, -50%)",
        transition: `left ${T}`,
      }}
    >
      {/* Cluster container */}
      <div
        className="relative pointer-events-auto"
        style={{
          width: clusterSize,
          height: clusterSize,
          transition: `width ${T}, height ${T}`,
        }}
        onMouseEnter={() => setClusterHovered(true)}
        onMouseLeave={() => {
          setClusterHovered(false);
          handleBubbleLeave();
        }}
      >
        {/* Avatar — click to go home on inner pages */}
        <button
          className="absolute cursor-pointer rounded-full"
          style={{
            left: center - avatarSize / 2,
            top: center - avatarSize / 2,
            transition: `left ${T}, top ${T}, box-shadow 300ms ease`,
            boxShadow: avatarGlow
              ? "0 0 24px 8px rgba(245, 130, 32, 0.4), 0 0 48px 16px rgba(245, 130, 32, 0.15)"
              : "none",
          }}
          onClick={() => !isHome && router.push("/")}
          aria-label="Home"
        >
          <ConnectedAvatar size={avatarSize} />
        </button>

        {/* Online indicator — below avatar, inside cluster */}
        {!isHome && (
          <div
            className="absolute flex items-center justify-center gap-1.5 font-mono text-[10px] pointer-events-none"
            style={{
              left: center,
              top: center + avatarSize / 2 + 20,
              transform: "translateX(-50%)",
              opacity: clusterHovered ? 0.7 : 0.3,
              transition: "opacity 300ms",
            }}
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--tigers-orange)]" />
            </span>
            <span className="text-zinc-500 whitespace-nowrap">online</span>
          </div>
        )}

        {/* Connector dots — hero mode only */}
        {NAV_BUBBLES.map((_, i) => {
          const angleRad = toRad(angles[i]);
          return CONNECTOR_SIZES.map((dotSz, ci) => {
            const connKey = `conn-${i}-${ci}`;
            const isConnVisible = visibleElements.has(connKey);
            const isGlowing = glowElements.has(connKey);
            const isHoverGlowing = hoverGlowSet.has(connKey);
            const t = 0.3 + ci * 0.25;
            const startDist = avatarRadius + 4;
            const endDist = orbitRadius - dotSize / 2 - 4;
            const dist = startDist + t * (endDist - startDist);
            return (
              <div
                key={`c-${i}-${ci}`}
                className="absolute rounded-full"
                style={{
                  left: center + dist * Math.cos(angleRad) - dotSz / 2,
                  top: center - dist * Math.sin(angleRad) - dotSz / 2,
                  width: dotSz,
                  height: dotSz,
                  backgroundColor:
                    isHoverGlowing || isGlowing
                      ? "rgba(245, 130, 32, 0.8)"
                      : hoveredIndex === i
                        ? "rgba(245, 130, 32, 0.35)"
                        : "rgba(255, 255, 255, 0.08)",
                  boxShadow: isHoverGlowing
                    ? "0 0 12px rgba(245, 130, 32, 0.7)"
                    : isGlowing
                      ? "0 0 8px rgba(245, 130, 32, 0.5)"
                      : "none",
                  opacity: isHome && isConnVisible ? 1 : 0,
                  transform: isConnVisible
                    ? isHoverGlowing ? "scale(1.4)" : "scale(1)"
                    : "scale(0)",
                  transition: `left ${T}, top ${T}, opacity 200ms, transform 200ms, background-color 200ms, box-shadow 200ms`,
                }}
              />
            );
          });
        })}

        {/* Nav bubbles */}
        {NAV_BUBBLES.map((bubble, i) => {
          const angleRad = toRad(angles[i]);
          const isActive = !isHome && pathname.startsWith(bubble.href);
          const isHovered = hoveredIndex === i;
          const bubbleKey = `bubble-${i}`;
          const isVisible = visibleElements.has(bubbleKey);
          const isBubbleGlowing = glowElements.has(bubbleKey);

          const hoverOrbit =
            !isHome && clusterHovered ? orbitRadius + 8 : orbitRadius;
          const x =
            center + hoverOrbit * Math.cos(angleRad) - dotSize / 2;
          const y =
            center - hoverOrbit * Math.sin(angleRad) - dotSize / 2;

          const Icon = bubble.icon;

          // Tooltip — radial direction, with viewport-edge awareness
          const angle = angles[i];
          const bubbleCenterX = center + hoverOrbit * Math.cos(angleRad);
          const bubbleCenterY = center - hoverOrbit * Math.sin(angleRad);
          let tooltipX = bubbleCenterX;
          let tooltipY = bubbleCenterY;
          let tooltipTransform = "translate(-50%, -100%)";

          if (angle > 110 && angle < 135) {
            // Upper-left (My Squad) — tooltip to the left
            tooltipX -= dotSize / 2 + 8;
            tooltipTransform = "translate(-100%, -50%)";
          } else if (angle > 45 && angle < 70) {
            // Upper-right (The Ledger) — tooltip to the right
            tooltipX += dotSize / 2 + 8;
            tooltipTransform = "translate(0%, -50%)";
          } else if (angle >= 70 && angle <= 110) {
            // Top center — tooltip above
            tooltipY -= dotSize / 2 + 8;
            tooltipTransform = "translate(-50%, -100%)";
          } else if (angle >= 135 && angle <= 225) {
            // Left side — tooltip to the left
            tooltipX -= dotSize / 2 + 8;
            tooltipTransform = "translate(-100%, -50%)";
          } else if (angle > 225 && angle < 315) {
            // Bottom — tooltip below
            tooltipY += dotSize / 2 + 8;
            tooltipTransform = "translate(-50%, 0%)";
          } else {
            // Right side — tooltip to the right
            tooltipX += dotSize / 2 + 8;
            tooltipTransform = "translate(0%, -50%)";
          }

          return (
            <div key={bubble.href}>
              <button
                className="absolute flex items-center justify-center rounded-full cursor-pointer focus:outline-none"
                style={{
                  left: x,
                  top: y,
                  width: dotSize,
                  height: dotSize,
                  backgroundColor:
                    isActive || isHovered || isBubbleGlowing
                      ? "rgba(245, 130, 32, 0.12)"
                      : "rgba(255, 255, 255, 0.04)",
                  border:
                    isActive || isHovered || isBubbleGlowing
                      ? "1.5px solid rgba(245, 130, 32, 0.5)"
                      : "1.5px solid rgba(255, 255, 255, 0.08)",
                  boxShadow: isActive || isBubbleGlowing
                    ? "0 0 16px rgba(245, 130, 32, 0.25)"
                    : isHovered
                      ? "0 0 8px rgba(245, 130, 32, 0.2)"
                      : "none",
                  transform: isVisible
                    ? isHovered
                      ? "scale(1.15)"
                      : "scale(1)"
                    : "scale(0)",
                  opacity: isVisible
                    ? !isHome && !clusterHovered && !isActive
                      ? 0.6
                      : 1
                    : 0,
                  animation:
                    isHome && isVisible
                      ? `thought-float 3s ease-in-out ${i * 0.4}s infinite`
                      : "none",
                  transition: `left ${T}, top ${T}, width ${T}, height ${T}, opacity 200ms, background-color 300ms, border 300ms, box-shadow 300ms, transform 200ms`,
                }}
                onClick={() => router.push(bubble.href)}
                onMouseEnter={() => handleBubbleHover(i)}
                onMouseLeave={handleBubbleLeave}
                aria-label={bubble.label}
              >
                <Icon
                  size={iconSize}
                  style={{
                    color:
                      isActive || isHovered || isBubbleGlowing
                        ? "var(--tigers-orange)"
                        : "rgba(255, 255, 255, 0.35)",
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
                    backgroundColor: "rgba(245, 130, 32, 0.12)",
                    color: "var(--tigers-orange)",
                    border: "1px solid rgba(245, 130, 32, 0.2)",
                  }}
                >
                  {bubble.label}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Hero content — landing page only, positioned below cluster */}
      <div
        className="absolute left-1/2 flex flex-col items-center text-center"
        style={{
          top: clusterSize - 100,
          transform: "translateX(-50%)",
          width: "max-content",
          opacity: isHome && !isTransitioning ? 1 : 0,
          transition: isHome
            ? `opacity ${CONTENT_FADE_MS}ms ease-in ${CONTENT_DELAY_MS}ms`
            : "opacity 200ms ease-out",
          pointerEvents: isHome ? "auto" : "none",
        }}
      >
        <JeromeluLogo key={logoKey} />
        <div className="mt-6">
          <CrewStatus />
        </div>
        <div className="mt-4">
          <LatestThought />
        </div>
        <div className="mt-3">
          <ActivityPulse />
        </div>
      </div>
    </div>
  );
}
