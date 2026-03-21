"use client";

import { useState, useEffect, useRef } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import JeromeluLogo from "./JeromeluLogo";
import { StatusLine } from "./StatusLine";
import { LatestThought } from "./LatestThought";
import { ActivityPulse } from "./ActivityPulse";
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
  { label: "Ask Me", href: "/ask", icon: MessageCircle },
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

const T = "900ms cubic-bezier(0.4, 0, 0.2, 1)";

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

export function JeromeluPresence() {
  const pathname = usePathname();
  const router = useRouter();
  const { triggerClip } = useAvatarEngine();
  const isHome = pathname === "/";
  const isAdmin = pathname.startsWith("/admin");

  // Hide presence on admin pages
  if (isAdmin) return null;

  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [clusterHovered, setClusterHovered] = useState(false);
  const [visibleSet, setVisibleSet] = useState<Set<number>>(new Set());
  const hasEnteredRef = useRef(false);

  // Staggered entrance — once only
  useEffect(() => {
    if (hasEnteredRef.current) return;
    hasEnteredRef.current = true;

    if (!isHome) {
      setVisibleSet(new Set([0, 1, 2, 3, 4]));
      return;
    }

    const timeouts: ReturnType<typeof setTimeout>[] = [];
    ENTRANCE_ORDER.forEach((bubbleIndex, step) => {
      const t = setTimeout(() => {
        setVisibleSet((prev) => {
          const next = new Set(prev);
          next.add(bubbleIndex);
          return next;
        });
      }, 600 + step * 120);
      timeouts.push(t);
    });
    return () => timeouts.forEach(clearTimeout);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Ensure all visible when leaving home
  useEffect(() => {
    if (!isHome) {
      setVisibleSet(new Set([0, 1, 2, 3, 4]));
    }
  }, [isHome]);

  const handleBubbleHover = (index: number) => {
    setHoveredIndex(index);
    const angles = isHome ? HERO_ANGLES : ORBITAL_ANGLES;
    const angle = angles[index];
    if (angle > 90 && angle < 270) {
      triggerClip("directional", "glance-left");
    } else if (angle < 90 || angle > 270) {
      triggerClip("directional", "glance-right");
    } else {
      triggerClip("directional", "glance-up");
    }
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
          setHoveredIndex(null);
        }}
      >
        {/* Avatar — click to go home on inner pages */}
        <button
          className="absolute cursor-pointer"
          style={{
            left: center - avatarSize / 2,
            top: center - avatarSize / 2,
            transition: `left ${T}, top ${T}`,
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
                    hoveredIndex === i
                      ? "rgba(245, 130, 32, 0.35)"
                      : "rgba(255, 255, 255, 0.08)",
                  opacity: isHome && visibleSet.has(i) ? 1 : 0,
                  transition: `left ${T}, top ${T}, opacity 300ms, background-color 200ms`,
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
          const isVisible = visibleSet.has(i);

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

          if (angle > 45 && angle < 135) {
            // Top — tooltip above
            tooltipY -= dotSize / 2 + 8;
            tooltipTransform = angle > 110
              ? "translate(0%, -100%)"   // near left edge
              : angle < 70
                ? "translate(-100%, -100%)" // near right edge
                : "translate(-50%, -100%)";
          } else if (angle >= 135 && angle <= 225) {
            // Left side — tooltip to the right (avoid left viewport edge)
            tooltipX += dotSize / 2 + 8;
            tooltipTransform = "translate(0%, -50%)";
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
                    isActive || isHovered
                      ? "rgba(245, 130, 32, 0.12)"
                      : "rgba(255, 255, 255, 0.04)",
                  border:
                    isActive || isHovered
                      ? "1.5px solid rgba(245, 130, 32, 0.5)"
                      : "1.5px solid rgba(255, 255, 255, 0.08)",
                  boxShadow: isActive
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
                  transition: `left ${T}, top ${T}, width ${T}, height ${T}, opacity 200ms, background-color 200ms, border 200ms, box-shadow 200ms, transform 200ms`,
                }}
                onClick={() => router.push(bubble.href)}
                onMouseEnter={() => handleBubbleHover(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                aria-label={bubble.label}
              >
                <Icon
                  size={iconSize}
                  style={{
                    color:
                      isActive || isHovered
                        ? "var(--tigers-orange)"
                        : "rgba(255, 255, 255, 0.35)",
                    transition: "color 200ms",
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

      {/* Hero content — landing page only, collapses when hidden */}
      {isHome && (
        <div
          className="flex flex-col items-center text-center pointer-events-auto"
          style={{ marginTop: -100 }}
        >
          <JeromeluLogo />
          <div className="mt-6">
            <StatusLine />
          </div>
          <div className="mt-4">
            <LatestThought />
          </div>
          <div className="mt-3">
            <ActivityPulse />
          </div>
        </div>
      )}
    </div>
  );
}
