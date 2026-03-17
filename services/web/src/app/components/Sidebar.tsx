"use client";

import { usePathname, useRouter } from "next/navigation";
import { LETTERS } from "./JeromeluLogo";
import type { LetterConfig } from "./JeromeluLogo";
import { useNavHover } from "./NavHoverContext";

const NAV_ITEMS: LetterConfig[] = LETTERS.filter(
  (letter, i, arr) => arr.findIndex((l) => l.href === letter.href) === i
);

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { hoveredHref, setHoveredHref } = useNavHover();

  // No sidebar on home page
  if (pathname === "/") return null;

  return (
    <aside
      className="group/sidebar fixed left-0 top-0 h-screen z-40 hidden lg:flex flex-col w-14 hover:w-52 transition-[width] duration-200 ease-in-out border-r"
      style={{
        backgroundColor: "rgb(0, 0, 0)",
        borderColor: "rgb(39, 39, 42)", // zinc-800
      }}
    >
      {/* Home link at top */}
      <button
        onClick={() => router.push("/")}
        className="flex items-center h-14 px-4 cursor-pointer shrink-0"
        style={{ borderBottom: "1px solid rgb(39, 39, 42)" }}
      >
        <span
          className="text-lg font-bold shrink-0"
          style={{ color: "var(--tigers-orange)" }}
        >
          J
        </span>
        <span
          className="ml-2 text-sm font-medium whitespace-nowrap overflow-hidden opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
          style={{ color: "rgb(161, 161, 170)" }} // zinc-400
        >
          Jeromelu
        </span>
      </button>

      {/* Nav items */}
      <nav className="flex flex-col py-2 flex-1">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);
          const isHovered = hoveredHref === item.href;

          return (
            <button
              key={item.href}
              onClick={() => router.push(item.href)}
              onMouseEnter={() => setHoveredHref(item.href)}
              onMouseLeave={() => setHoveredHref(null)}
              className="relative flex items-center h-11 px-4 gap-3 cursor-pointer"
              style={{
                backgroundColor: isHovered
                  ? "rgba(245, 130, 32, 0.08)"
                  : "transparent",
                transition: "background-color 150ms",
              }}
            >
              {/* Active indicator */}
              {isActive && (
                <span
                  className="absolute left-0 top-2 bottom-2 w-[3px] rounded-r"
                  style={{ backgroundColor: "var(--tigers-orange)" }}
                />
              )}
              <Icon
                size={18}
                className="shrink-0"
                style={{
                  color:
                    isActive || isHovered
                      ? "var(--tigers-orange)"
                      : "rgba(255, 255, 255, 0.4)",
                  transition: "color 150ms",
                }}
              />
              <span
                className="text-sm whitespace-nowrap overflow-hidden opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
                style={{
                  color:
                    isActive || isHovered
                      ? "var(--tigers-orange)"
                      : "rgb(161, 161, 170)", // zinc-400
                }}
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
