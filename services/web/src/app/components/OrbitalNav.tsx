"use client";

import { useState, useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ConnectedAvatar } from "./ConnectedAvatar";
import { useAvatarEngine } from "./AvatarEngine";
import {
  Activity,
  Users,
  FileText,
  BookOpen,
  MessageCircle,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface NavDot {
  label: string;
  href: string;
  icon: LucideIcon;
}

const NAV_DOTS: NavDot[] = [
  { label: "The Feed", href: "/feed", icon: Activity },
  { label: "My Squad", href: "/squad", icon: Users },
  { label: "The Dossier", href: "/dossier", icon: FileText },
  { label: "The Ledger", href: "/ledger", icon: BookOpen },
  { label: "Ask Me", href: "/feed", icon: MessageCircle },
];

// 5 dots spread evenly across a full circle
// Starting from top (90°), going clockwise: 90, 18, 306, 234, 162
const ANGLES_DEG = [90, 18, 306, 234, 162];

const AVATAR_SIZE = 160;
const DOT_SIZE = 42;
const AVATAR_RADIUS = AVATAR_SIZE / 2;
const GAP = 18;
const ORBIT_RADIUS = AVATAR_RADIUS + GAP + DOT_SIZE / 2;
const CLUSTER_SIZE = (ORBIT_RADIUS + DOT_SIZE / 2 + 4) * 2;
const CENTER = CLUSTER_SIZE / 2;

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

export function OrbitalNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { triggerClip } = useAvatarEngine();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [clusterHovered, setClusterHovered] = useState(false);

  // Don't render on home page
  if (pathname === "/") return null;

  const handleDotHover = (index: number) => {
    setHoveredIndex(index);
    const angle = ANGLES_DEG[index];
    if (angle > 90 && angle < 270) {
      triggerClip("directional", "glance-left");
    } else if (angle < 90 || angle > 270) {
      triggerClip("directional", "glance-right");
    } else {
      triggerClip("directional", "glance-up");
    }
  };

  return (
    <div
      className="fixed z-50"
      style={{
        top: "50%",
        left: "calc((100vw - 48rem) / 4)",
        transform: "translate(-50%, -50%)",
      }}
      onMouseEnter={() => setClusterHovered(true)}
      onMouseLeave={() => {
        setClusterHovered(false);
        setHoveredIndex(null);
      }}
    >
      <div
        className="relative"
        style={{ width: CLUSTER_SIZE, height: CLUSTER_SIZE }}
      >
        {/* Avatar in center — click to go home */}
        <button
          className="absolute cursor-pointer"
          style={{
            left: CENTER - AVATAR_SIZE / 2,
            top: CENTER - AVATAR_SIZE / 2,
          }}
          onClick={() => router.push("/")}
          aria-label="Home"
        >
          <ConnectedAvatar size={AVATAR_SIZE} />
        </button>

        {/* Orbiting nav dots */}
        {NAV_DOTS.map((dot, i) => {
          const angleRad = toRad(ANGLES_DEG[i]);
          const isActive = pathname.startsWith(dot.href);
          const isHovered = hoveredIndex === i;

          // Spread out slightly on cluster hover
          const activeOrbit = clusterHovered
            ? ORBIT_RADIUS + 8
            : ORBIT_RADIUS;
          const dx = CENTER + activeOrbit * Math.cos(angleRad) - DOT_SIZE / 2;
          const dy = CENTER - activeOrbit * Math.sin(angleRad) - DOT_SIZE / 2;

          const Icon = dot.icon;

          // Tooltip position: radially outward from the dot
          const tooltipDist = activeOrbit + DOT_SIZE / 2 + 10;
          const tooltipX = CENTER + tooltipDist * Math.cos(angleRad);
          const tooltipY = CENTER - tooltipDist * Math.sin(angleRad);

          // Determine tooltip alignment based on angle
          const angle = ANGLES_DEG[i];
          let tooltipTransform = "translate(-50%, -50%)";
          if (angle > 45 && angle < 135) {
            // Top — anchor bottom-center
            tooltipTransform = "translate(-50%, -100%)";
          } else if (angle > 225 && angle < 315) {
            // Bottom — anchor top-center
            tooltipTransform = "translate(-50%, 0%)";
          } else if (angle >= 135 && angle <= 225) {
            // Left — anchor right
            tooltipTransform = "translate(-100%, -50%)";
          } else {
            // Right — anchor left
            tooltipTransform = "translate(0%, -50%)";
          }

          return (
            <div key={dot.href}>
              {/* Nav dot */}
              <button
                className="absolute flex items-center justify-center rounded-full cursor-pointer focus:outline-none"
                style={{
                  left: dx,
                  top: dy,
                  width: DOT_SIZE,
                  height: DOT_SIZE,
                  backgroundColor:
                    isActive || isHovered
                      ? "rgba(245, 130, 32, 0.15)"
                      : "rgba(255, 255, 255, 0.04)",
                  border:
                    isActive || isHovered
                      ? "1.5px solid rgba(245, 130, 32, 0.5)"
                      : "1.5px solid rgba(255, 255, 255, 0.08)",
                  boxShadow:
                    isActive
                      ? "0 0 12px rgba(245, 130, 32, 0.3)"
                      : isHovered
                        ? "0 0 8px rgba(245, 130, 32, 0.2)"
                        : "none",
                  transform: isHovered ? "scale(1.15)" : "scale(1)",
                  opacity: clusterHovered ? 1 : 0.6,
                  transition:
                    "all 200ms ease-out",
                }}
                onClick={() => router.push(dot.href)}
                onMouseEnter={() => handleDotHover(i)}
                onMouseLeave={() => setHoveredIndex(null)}
                aria-label={dot.label}
              >
                <Icon
                  size={18}
                  style={{
                    color:
                      isActive || isHovered
                        ? "var(--tigers-orange)"
                        : "rgba(255, 255, 255, 0.35)",
                    transition: "color 200ms",
                  }}
                />
              </button>

              {/* Tooltip label */}
              {(isHovered || (clusterHovered && isActive)) && (
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
                  {dot.label}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Subtle status line below cluster */}
      <div
        className="flex items-center justify-center gap-1.5 -mt-2 font-mono text-[10px]"
        style={{
          opacity: clusterHovered ? 0.7 : 0.3,
          transition: "opacity 300ms",
        }}
      >
        <span className="relative flex h-1.5 w-1.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--tigers-orange)] opacity-75" />
          <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-[var(--tigers-orange)]" />
        </span>
        <span className="text-zinc-500">online</span>
      </div>
    </div>
  );
}
