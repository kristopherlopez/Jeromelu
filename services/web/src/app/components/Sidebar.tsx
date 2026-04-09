"use client";

import { usePathname, useRouter } from "next/navigation";
import { LETTERS } from "./JeromeluLogo";
import type { LetterConfig } from "./JeromeluLogo";
import { useNavHover } from "./NavHoverContext";
import { useTheme } from "./ThemeContext";

const NAV_ITEMS: LetterConfig[] = LETTERS.filter(
  (letter, i, arr) => arr.findIndex((l) => l.href === letter.href) === i
);

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { hoveredHref, setHoveredHref } = useNavHover();
  const { isLight: isWiki } = useTheme();

  // No sidebar on home page
  if (pathname === "/landing") return null;

  const accent = isWiki ? "#b85c38" : "var(--accent)";
  const faint = isWiki ? "#9c9484" : "var(--foreground-secondary)";
  const iconDefault = isWiki ? "rgba(28, 26, 20, 0.35)" : "rgba(255, 255, 255, 0.4)";
  const hoverBg = isWiki ? "rgba(184, 92, 56, 0.08)" : "var(--accent-bg)";
  const borderColor = isWiki ? "rgba(28,26,20,0.12)" : "var(--border)";

  return (
    <aside
      className="group/sidebar fixed left-0 top-0 h-screen z-40 hidden lg:flex flex-col w-14 hover:w-52 transition-[width] duration-200 ease-in-out border-r"
      style={{
        backgroundColor: isWiki ? "#F5F4F0" : "var(--background-deep)",
        borderColor,
      }}
    >
      {/* Home link at top */}
      <button
        onClick={() => router.push("/landing")}
        className="flex items-center h-14 px-4 cursor-pointer shrink-0"
        style={{ borderBottom: `1px solid ${borderColor}` }}
      >
        <span className="text-lg font-bold shrink-0" style={{ color: accent }}>
          J
        </span>
        <span
          className="ml-2 text-sm font-medium whitespace-nowrap overflow-hidden opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
          style={{ color: faint }}
        >
          Jaromelu
        </span>
      </button>

      {/* Nav items */}
      <nav className="flex flex-col py-2 flex-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/" ? pathname === "/landing" : pathname.startsWith(item.href);
          const isHovered = hoveredHref === item.href;

          return (
            <button
              key={item.href}
              onClick={() => router.push(item.href)}
              onMouseEnter={() => setHoveredHref(item.href)}
              onMouseLeave={() => setHoveredHref(null)}
              className="relative flex items-center h-11 px-4 gap-3 cursor-pointer"
              style={{
                backgroundColor: isHovered ? hoverBg : "transparent",
                transition: "background-color 150ms",
              }}
            >
              {isActive && (
                <span
                  className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r"
                  style={{ backgroundColor: accent }}
                />
              )}
              <Icon
                size={18}
                className="shrink-0"
                style={{
                  color: isActive || isHovered ? accent : iconDefault,
                  transition: "color 150ms",
                }}
              />
              <span
                className="text-sm whitespace-nowrap overflow-hidden opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
                style={{ color: isActive || isHovered ? accent : faint }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
