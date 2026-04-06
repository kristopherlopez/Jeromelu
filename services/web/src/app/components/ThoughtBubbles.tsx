"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useAvatarEngine } from "./AvatarEngine";
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

// 5 bubbles spread evenly across the top of the circle (210° to 330° in standard math,
// or equivalently from upper-left to upper-right going over the top)
// Using angles measured from 3 o'clock, going counter-clockwise:
// We want them across the top half: 200° to 340° (sweeping over the top)
// Angles measured counter-clockwise from 3 o'clock position
// Top of circle = 90°. We spread 5 bubbles across the upper arc.
const ANGLES_DEG = [170, 132, 90, 48, 10];

// Entrance order: center first, then outward
const ENTRANCE_ORDER = [2, 1, 3, 0, 4];

const BUBBLE_SIZE = 60;
const CONNECTOR_SIZES = [5, 11]; // small dots between bubble and avatar edge

function toRad(deg: number) {
  return (deg * Math.PI) / 180;
}

interface ThoughtBubblesProps {
  avatarSize: number;
}

export function ThoughtBubbles({ avatarSize }: ThoughtBubblesProps) {
  const router = useRouter();
  const { triggerClip } = useAvatarEngine();
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [visibleSet, setVisibleSet] = useState<Set<number>>(new Set());

  // Trigger directional glance on bubble hover
  const handleBubbleHover = useCallback(
    (index: number) => {
      setHoveredIndex(index);
      const angle = ANGLES_DEG[index];
      // Left side of arc (angle > 90) → glance left, right side → glance right
      const direction = angle > 90 ? "glance-left" : angle < 90 ? "glance-right" : "glance-up";
      triggerClip("directional", direction);
    },
    [triggerClip],
  );

  // Staggered entrance animation
  useEffect(() => {
    const timeouts: ReturnType<typeof setTimeout>[] = [];
    ENTRANCE_ORDER.forEach((bubbleIndex, step) => {
      const t = setTimeout(
        () => {
          setVisibleSet((prev) => {
            const next = new Set(prev);
            next.add(bubbleIndex);
            return next;
          });
        },
        600 + step * 120,
      );
      timeouts.push(t);
    });
    return () => timeouts.forEach(clearTimeout);
  }, []);

  // Concentric layout: bubbles orbit at a fixed distance from the avatar edge
  const avatarRadius = avatarSize / 2;
  const gap = 50; // space between avatar edge and bubble center
  const orbitRadius = avatarRadius + gap + BUBBLE_SIZE / 2;

  // Container sized to fit the full orbit
  const containerSize = (orbitRadius + BUBBLE_SIZE / 2 + 8) * 2;
  const center = containerSize / 2;

  return (
    <div
      className="pointer-events-none relative"
      style={{ width: containerSize, height: containerSize }}
    >
      {NAV_BUBBLES.map((bubble, i) => {
        const angleRad = toRad(ANGLES_DEG[i]);
        const isVisible = visibleSet.has(i);
        const isHovered = hoveredIndex === i;

        // Bubble center position on the orbit circle
        const bx = center + orbitRadius * Math.cos(angleRad) - BUBBLE_SIZE / 2;
        const by = center - orbitRadius * Math.sin(angleRad) - BUBBLE_SIZE / 2;

        // Connector dots along the line from avatar edge to bubble
        const connectors = CONNECTOR_SIZES.map((dotSize, ci) => {
          const t = 0.3 + ci * 0.25;
          const startDist = avatarRadius + 4;
          const endDist = orbitRadius - BUBBLE_SIZE / 2 - 4;
          const dist = startDist + t * (endDist - startDist);
          return {
            x: center + dist * Math.cos(angleRad) - dotSize / 2,
            y: center - dist * Math.sin(angleRad) - dotSize / 2,
            size: dotSize,
          };
        });

        const Icon = bubble.icon;

        // Tooltip position: above the bubble
        const bubbleCenterX = center + orbitRadius * Math.cos(angleRad);
        const bubbleCenterY = center - orbitRadius * Math.sin(angleRad);
        const tooltipX = bubbleCenterX;
        const tooltipY = bubbleCenterY - BUBBLE_SIZE / 2 - 14;

        return (
          <div key={bubble.href}>
            {/* Connector dots */}
            {connectors.map((dot, ci) => (
              <div
                key={ci}
                className="absolute rounded-full"
                style={{
                  left: dot.x,
                  top: dot.y,
                  width: dot.size,
                  height: dot.size,
                  backgroundColor: isHovered
                    ? "rgba(245, 130, 32, 0.35)"
                    : "rgba(255, 255, 255, 0.08)",
                  opacity: isVisible ? 1 : 0,
                  transition: "opacity 200ms, background-color 200ms",
                }}
              />
            ))}

            {/* Bubble */}
            <button
              className="pointer-events-auto absolute flex items-center justify-center rounded-full transition-all duration-200 cursor-pointer focus:outline-none"
              style={{
                left: bx,
                top: by,
                width: BUBBLE_SIZE,
                height: BUBBLE_SIZE,
                backgroundColor: isHovered
                  ? "rgba(245, 130, 32, 0.12)"
                  : "rgba(255, 255, 255, 0.10)",
                border: isHovered
                  ? "1.5px solid rgba(245, 130, 32, 0.5)"
                  : "1.5px solid rgba(255, 255, 255, 0.18)",
                transform: isVisible
                  ? isHovered
                    ? "scale(1.15)"
                    : "scale(1)"
                  : "scale(0)",
                opacity: isVisible ? 1 : 0,
                animation: isVisible
                  ? `thought-float 3s ease-in-out ${i * 0.4}s infinite`
                  : "none",
                boxShadow: isHovered
                  ? "0 0 16px rgba(245, 130, 32, 0.25)"
                  : "none",
              }}
              onClick={() => router.push(bubble.href)}
              onMouseEnter={() => handleBubbleHover(i)}
              onMouseLeave={() => setHoveredIndex(null)}
              aria-label={bubble.label}
            >
              <Icon
                size={20}
                style={{
                  color: isHovered
                    ? "var(--tigers-orange)"
                    : "rgba(255, 255, 255, 0.55)",
                  transition: "color 200ms",
                }}
              />
            </button>

            {/* Tooltip label — positioned above the bubble */}
            {isHovered && isVisible && (
              <div
                className="absolute whitespace-nowrap rounded-md px-2.5 py-1 text-[11px] font-medium pointer-events-none"
                style={{
                  left: tooltipX,
                  top: tooltipY,
                  transform: "translate(-50%, -100%)",
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
  );
}
