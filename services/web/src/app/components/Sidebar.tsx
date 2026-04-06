"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { LETTERS } from "./JeromeluLogo";
import type { LetterConfig } from "./JeromeluLogo";
import { useNavHover } from "./NavHoverContext";
import { useIsWiki } from "../wiki/useIsWiki";
import type { WikiChangeItem, WikiPageType } from "../wiki/wiki-data";

const NAV_ITEMS: LetterConfig[] = LETTERS.filter(
  (letter, i, arr) => arr.findIndex((l) => l.href === letter.href) === i
);

const API_BASE = process.env.NEXT_PUBLIC_API_URL!;

function formatRelative(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;
  return new Date(iso).toLocaleDateString("en-AU", { day: "numeric", month: "short" });
}

function changeHref(change: WikiChangeItem): string {
  if (change.page_type === "round") {
    const match = change.page_slug.match(/^round-(\d+)-(\d+)$/);
    if (match) return `/wiki/round/${match[1]}/${match[2]}`;
  }
  return `/wiki/${change.page_type}/${change.page_slug}`;
}

export default function Sidebar() {
  const router = useRouter();
  const pathname = usePathname();
  const { hoveredHref, setHoveredHref } = useNavHover();
  const isWiki = useIsWiki();
  const [recentChanges, setRecentChanges] = useState<WikiChangeItem[]>([]);

  // Fetch recent changes when on wiki pages
  useEffect(() => {
    if (!isWiki) {
      setRecentChanges([]);
      return;
    }
    fetch(`${API_BASE}/api/wiki/recent-changes?limit=8`)
      .then((r) => r.json())
      .then((d) => setRecentChanges(d.items || []))
      .catch(() => {});
  }, [isWiki]);

  // No sidebar on home page
  if (pathname === "/") return null;

  const accent = isWiki ? "#b85c38" : "var(--tigers-orange)";
  const faint = isWiki ? "#9c9484" : "rgb(161, 161, 170)";
  const iconDefault = isWiki ? "rgba(28, 26, 20, 0.35)" : "rgba(255, 255, 255, 0.4)";
  const hoverBg = isWiki ? "rgba(184, 92, 56, 0.08)" : "rgba(245, 130, 32, 0.08)";
  const borderColor = isWiki ? "rgba(28,26,20,0.12)" : "rgb(39, 39, 42)";

  return (
    <aside
      className="group/sidebar fixed left-0 top-0 h-screen z-40 hidden lg:flex flex-col w-14 hover:w-52 transition-[width] duration-200 ease-in-out border-r"
      style={{
        backgroundColor: isWiki ? "#f0ebe2" : "rgb(0, 0, 0)",
        borderColor,
      }}
    >
      {/* Home link at top */}
      <button
        onClick={() => router.push("/")}
        className="flex items-center h-14 px-4 cursor-pointer shrink-0"
        style={{ borderBottom: `1px solid ${borderColor}` }}
      >
        <span
          className="text-lg font-bold shrink-0"
          style={{ color: accent }}
        >
          J
        </span>
        <span
          className="ml-2 text-sm font-medium whitespace-nowrap overflow-hidden opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200"
          style={{ color: faint }}
        >
          Jeromelu
        </span>
      </button>

      {/* Nav items */}
      <nav className="flex flex-col py-2">
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
                style={{
                  color: isActive || isHovered ? accent : faint,
                }}
              >
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      {/* Recent changes — wiki only, visible on hover */}
      {isWiki && recentChanges.length > 0 && (
        <div
          className="flex-1 overflow-y-auto opacity-0 group-hover/sidebar:opacity-100 transition-opacity duration-200 px-3 pb-3"
          style={{ borderTop: `1px solid ${borderColor}` }}
        >
          <p
            className="pt-3 pb-2 whitespace-nowrap overflow-hidden"
            style={{
              fontSize: "10px",
              fontWeight: 600,
              letterSpacing: "0.1em",
              textTransform: "uppercase" as const,
              color: faint,
            }}
          >
            Recent Changes
          </p>
          <ul className="space-y-2" style={{ listStyle: "none", margin: 0, padding: 0 }}>
            {recentChanges.map((change) => (
              <li key={change.revision_id} className="whitespace-nowrap overflow-hidden">
                <Link
                  href={changeHref(change)}
                  className="block text-xs truncate"
                  style={{ color: accent, textDecoration: "none", fontWeight: 500 }}
                >
                  {change.page_title}
                </Link>
                <p
                  className="truncate"
                  style={{ fontSize: "11px", color: isWiki ? "#5c5848" : "rgb(113,113,122)", margin: 0, lineHeight: 1.4 }}
                >
                  {change.summary}
                </p>
                <span style={{ fontSize: "10px", color: faint }}>
                  {formatRelative(change.created_at)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </aside>
  );
}
