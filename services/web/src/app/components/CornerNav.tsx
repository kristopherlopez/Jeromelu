"use client";

import { usePathname, useRouter } from "next/navigation";
import { LETTERS } from "./JeromeluLogo";
import type { LetterConfig } from "./JeromeluLogo";
import { useNavHover } from "./NavHoverContext";

// Deduplicate letters by href (both "e"s point to /energy)
const NAV_ITEMS: LetterConfig[] = LETTERS.filter(
  (letter, i, arr) => arr.findIndex((l) => l.href === letter.href) === i
);

export default function CornerNav() {
  const router = useRouter();
  const pathname = usePathname();
  const { hoveredHref, setHoveredHref } = useNavHover();

  return (
    <nav className="fixed bottom-6 right-6 z-50 flex flex-col gap-3">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const isActive = pathname === item.href;
        const isHovered = hoveredHref === item.href;

        return (
          <button
            key={item.href}
            onClick={() => router.push(item.href)}
            onMouseEnter={() => setHoveredHref(item.href)}
            onMouseLeave={() => setHoveredHref(null)}
            className="group relative flex h-9 w-9 items-center justify-center rounded-full border cursor-pointer"
            style={{
              borderColor: isActive
                ? "var(--tigers-orange)"
                : isHovered
                  ? "rgba(245, 130, 32, 0.5)"
                  : "rgba(255, 255, 255, 0.1)",
              backgroundColor: isActive
                ? "rgba(245, 130, 32, 0.15)"
                : isHovered
                  ? "rgba(245, 130, 32, 0.08)"
                  : "rgba(0, 0, 0, 0.6)",
              backdropFilter: "blur(8px)",
              transform: isHovered ? "scale(1.2)" : "scale(1)",
              boxShadow: isHovered
                ? "0 0 12px rgba(245, 130, 32, 0.3), 0 0 24px rgba(245, 130, 32, 0.15)"
                : isActive
                  ? "0 0 8px rgba(245, 130, 32, 0.2)"
                  : "none",
              transition: "all 250ms cubic-bezier(0.4, 0, 0.2, 1)",
            }}
            aria-label={`${item.label} (press ${item.key})`}
          >
            <Icon
              size={16}
              style={{
                color: isActive || isHovered
                  ? "var(--tigers-orange)"
                  : "rgba(255, 255, 255, 0.4)",
                filter: isHovered
                  ? "drop-shadow(0 0 4px rgba(245, 130, 32, 0.5))"
                  : "none",
                transition: "color 250ms, filter 250ms",
              }}
            />
            {/* Tooltip on hover */}
            <span
              className="pointer-events-none absolute right-full mr-3 whitespace-nowrap rounded-md px-2 py-1 text-xs"
              style={{
                opacity: isHovered ? 1 : 0,
                transform: isHovered ? "translateX(0)" : "translateX(4px)",
                color: "var(--tigers-orange)",
                backgroundColor: "rgba(0, 0, 0, 0.8)",
                border: "1px solid rgba(245, 130, 32, 0.3)",
                transition: "opacity 200ms, transform 200ms",
              }}
            >
              {item.label}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
